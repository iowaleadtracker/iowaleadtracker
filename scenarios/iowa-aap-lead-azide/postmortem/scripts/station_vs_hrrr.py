"""Compare station surface winds with the HRRR analysis at each station.

Usage::

    HYSPLIT_DIR=/path/to/hysplit python station_vs_hrrr.py ARL_DIR ARL_FILE OBS_DIR > out.json

ARL_FILE holds the 15 and 16 UTC analyses (nowcast_hrrr.sh). OBS_DIR holds the Iowa
Environmental Mesonet downloads in ``data/obs``: station positions (station_coords.csv),
airport reports (asos_region_20261125.csv) and Iowa DOT road weather
(rwis_IA_20261125.csv). Reports within 20 minutes of the hour are vector-averaged; the
analysis is its 10 m wind, rotated from grid to true north with the rotation HYSPLIT's
profile tool reports for the lowest level.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

LAT0, LON0 = 40.8255, -91.2665
KT_PER_MS = 1 / 0.5144
WINDOW_S = 20 * 60
HOURS = (15, 16)
NEAR_MI = 16


def station_coords(obs: Path) -> dict[str, tuple[float, float, str]]:
    """Return {station id: (lat, lon, name)} from ``station_coords.csv``."""
    with (obs / "station_coords.csv").open() as f:
        return {
            r["station"]: (float(r["lat"]), float(r["lon"]), r["name"]) for r in csv.DictReader(f)
        }


def reports(obs: Path) -> dict[str, list[tuple[dt.datetime, float, float]]]:
    """Return {station: [(time, direction, speed kt)]} from airport and road reports."""
    out: dict[str, list[tuple[dt.datetime, float, float]]] = {}
    with (obs / "asos_region_20261125.csv").open() as f:
        for r in csv.DictReader(f):
            if r["drct"] not in ("M", "") and r["sknt"] not in ("M", ""):
                t = dt.datetime.strptime(r["valid"], "%Y-%m-%d %H:%M")  # noqa: DTZ007 (UTC)
                out.setdefault(r["station"], []).append((t, float(r["drct"]), float(r["sknt"])))
    with (obs / "rwis_IA_20261125.csv").open() as f:
        for r in csv.DictReader(f):
            if r["drct"] and r["sknt"]:
                t = dt.datetime.strptime(r["obtime"], "%Y-%m-%d %H:%M:%S")  # noqa: DTZ007 (UTC)
                out.setdefault(r["station"], []).append((t, float(r["drct"]), float(r["sknt"])))
    return out


def analysis_wind(arl_dir: str, arl: str, lat: float, lon: float) -> dict[int, tuple[float, float]]:
    """Return {hour UTC: (direction, speed kt)} of the analysis 10 m wind at a point."""
    exe = Path(os.environ["HYSPLIT_DIR"]) / "exec" / "profile"
    with tempfile.TemporaryDirectory() as tmp:
        args = [str(exe), f"-d{arl_dir}/", f"-f{arl}", f"-y{lat}", f"-x{lon}", "-t1"]
        subprocess.run(args, cwd=tmp, check=True, capture_output=True)  # noqa: S603
        text = (Path(tmp) / "profile.txt").read_text()
    out = {}
    for block in text.split("Profile Time")[1:]:
        lines = block.splitlines()
        hour = int(lines[0].split()[4])
        i = next(k for k, line in enumerate(lines) if "SHGT" in line and "U10M" in line)
        v = lines[i + 2].split()
        gu, gv = float(v[-2]), float(v[-1])
        rot = 0.0
        for line in lines:
            p = line.split()
            if len(p) == 11:
                try:
                    a, b, tu, tv = float(p[3]), float(p[4]), float(p[-2]), float(p[-1])
                except ValueError:
                    continue
                rot = math.atan2(tv, tu) - math.atan2(b, a)
                break
        c, s = math.cos(rot), math.sin(rot)
        u, w = gu * c - gv * s, gu * s + gv * c
        out[hour] = ((math.degrees(math.atan2(-u, -w)) + 360) % 360, math.hypot(u, w) * KT_PER_MS)
    return out


def compare(arl_dir: str, arl: str, obs: Path) -> list[dict[str, Any]]:
    """Return one row per station and hour with observed and analyzed wind."""
    coords = station_coords(obs)
    rows = []
    for st, ob in reports(obs).items():
        if st not in coords:
            continue
        la, lo, name = coords[st]
        dy = (la - LAT0) * 111.195
        dx = (lo - LON0) * 111.195 * math.cos(math.radians(LAT0))
        hrrr = analysis_wind(arl_dir, arl, la, lo)
        for hour in HOURS:
            t = dt.datetime(2026, 11, 25, hour)  # noqa: DTZ001 (UTC)
            near = [o for o in ob if abs((o[0] - t).total_seconds()) <= WINDOW_S]
            if not near:
                continue
            u = sum(-k * math.sin(math.radians(d)) for _, d, k in near) / len(near)
            v = sum(-k * math.cos(math.radians(d)) for _, d, k in near) / len(near)
            obs_dir = (math.degrees(math.atan2(-u, -v)) + 360) % 360
            obs_kt = sum(k for _, _, k in near) / len(near)
            h_dir, h_kt = hrrr[hour]
            rows.append(
                {
                    "station": st,
                    "name": name,
                    "miles": math.hypot(dx, dy) / 1.609344,
                    "bearing": (math.degrees(math.atan2(dx, dy)) + 360) % 360,
                    "hour_utc": hour,
                    "obs_dir": obs_dir,
                    "obs_kt": obs_kt,
                    "n_reports": len(near),
                    "hrrr_dir": h_dir,
                    "hrrr_kt": h_kt,
                    "dir_error": (h_dir - obs_dir + 180) % 360 - 180,
                    "speed_error_kt": h_kt - obs_kt,
                }
            )
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Return mean, median and mean absolute errors by hour and station group."""
    out: dict[str, Any] = {}
    groups = {
        "all": lambda _: True,
        "airports": lambda r: not r["station"].endswith("I4"),
        "road stations": lambda r: r["station"].endswith("I4"),
        f"within {NEAR_MI} miles": lambda r: r["miles"] <= NEAR_MI,
    }
    for hour in HOURS:
        for name, keep in groups.items():
            sel = [r for r in rows if r["hour_utc"] == hour and keep(r)]
            if not sel:
                continue
            d = sorted(r["dir_error"] for r in sel)
            u = sum(-r["obs_kt"] * math.sin(math.radians(r["obs_dir"])) for r in sel)
            v = sum(-r["obs_kt"] * math.cos(math.radians(r["obs_dir"])) for r in sel)
            out[f"{hour} UTC, {name}"] = {
                "n": len(sel),
                "mean_dir_error": sum(d) / len(d),
                "median_dir_error": d[len(d) // 2],
                "mean_abs_dir_error": sum(abs(x) for x in d) / len(d),
                "mean_speed_error_kt": sum(r["speed_error_kt"] for r in sel) / len(sel),
                "observed_vector_mean_dir": (math.degrees(math.atan2(-u, -v)) + 360) % 360,
            }
    return out


if __name__ == "__main__":
    arl_dir, arl, obs = sys.argv[1:4]
    table = compare(arl_dir, arl, Path(obs))
    json.dump({"summary": summarize(table), "stations": table}, sys.stdout, indent=1)
    sys.stdout.write("\n")
