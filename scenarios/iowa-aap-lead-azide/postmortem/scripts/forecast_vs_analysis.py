"""Compare the forecast wind at the plant with the HRRR analysis at the same hours.

Usage::

    HYSPLIT_DIR=/path/to/hysplit python forecast_vs_analysis.py MET_CACHE ARL_DIR ARL_FILE

MET_CACHE is the tracker's saved forecast (``met_cache/map_met_all.json`` at the commit
being checked); the HRRR grid request's center point is the plant. ARL_FILE holds the
hourly analyses (``blast-day/nowcast_hrrr.sh``). Both are read at the top of each hour,
so the valid times match. Prints JSON: per hour, the forecast and analysis wind at 10 m
and on the pressure levels below 1 km, with heights above ground from each source.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

LAT, LON = 40.825518, -91.266502
LEVELS = (1000, 975, 950, 925, 900)
CENTER = 12  # index of the plant in the tracker's 5 x 5 wind grid
LEVEL_ROW_FIELDS = 11  # a 3-D row of HYSPLIT's profile.txt


def forecast(cache: Path) -> dict[int, list[dict[str, Any]]]:
    """Return {hour UTC: [level rows]} of the saved HRRR forecast at the plant."""
    d = json.loads(cache.read_text())
    key = next(
        k
        for k in d
        if k.startswith("http")
        and "ncep_hrrr_conus" in k
        and "end_date=2026-11-25" in k
        and "latitude=40.8255&" not in k
    )
    grid = d[key] if not isinstance(d[key], str) else json.loads(d[key])
    c, elev = grid[CENTER]["hourly"], grid[CENTER]["elevation"]
    out = {}
    for i, t in enumerate(c["time"]):
        if not t.startswith("2026-11-25T"):
            continue
        rows = [
            {
                "level": "10 m",
                "agl_m": 10,
                "ms": c["wind_speed_10m"][i],
                "from": c["wind_direction_10m"][i],
            },
            {
                "level": "80 m",
                "agl_m": 80,
                "ms": c["wind_speed_80m"][i],
                "from": c["wind_direction_80m"][i],
            },
        ]
        rows += [
            {
                "level": f"{p} hPa",
                "agl_m": c[f"geopotential_height_{p}hPa"][i] - elev,
                "ms": c[f"wind_speed_{p}hPa"][i],
                "from": c[f"wind_direction_{p}hPa"][i],
            }
            for p in LEVELS
        ]
        out[int(t[11:13])] = rows
    return out


def _dir(u: float, v: float) -> float:
    return (math.degrees(math.atan2(-u, -v)) + 360) % 360


def analysis(arl_dir: str, arl: str) -> dict[int, list[dict[str, Any]]]:
    """Return {hour UTC: [level rows]} of the analysis at the plant (HYSPLIT's profile)."""
    exe = Path(os.environ["HYSPLIT_DIR"]) / "exec" / "profile"
    with tempfile.TemporaryDirectory() as tmp:
        args = [str(exe), f"-d{arl_dir}/", f"-f{arl}", f"-y{LAT}", f"-x{LON}", "-t1"]
        subprocess.run(args, cwd=tmp, check=True, capture_output=True)  # noqa: S603
        text = (Path(tmp) / "profile.txt").read_text()
    out = {}
    for block in text.split("Profile Time")[1:]:
        lines = block.splitlines()
        hour = int(lines[0].split()[4])
        i = next(k for k, line in enumerate(lines) if "SHGT" in line and "U10M" in line)
        v2 = lines[i + 2].split()
        sfc, gu, gv = float(v2[1]), float(v2[-2]), float(v2[-1])
        rows: list[dict[str, Any]] = []
        rot = None
        for line in lines:
            p = line.split()
            if len(p) != LEVEL_ROW_FIELDS:
                continue
            try:
                pres, z, a, b, tu, tv = (float(p[k]) for k in (0, 1, 3, 4, -2, -1))
            except ValueError:
                continue
            if rot is None:  # grid-to-true rotation, from the lowest level
                rot = math.atan2(tv, tu) - math.atan2(b, a)
            if int(pres) in LEVELS:
                rows.append(
                    {
                        "level": f"{int(pres)} hPa",
                        "agl_m": z - sfc,
                        "ms": math.hypot(tu, tv),
                        "from": _dir(tu, tv),
                    }
                )
        c, s = math.cos(rot or 0.0), math.sin(rot or 0.0)
        u, v = gu * c - gv * s, gu * s + gv * c
        out[hour] = [
            {"level": "10 m", "agl_m": 10, "ms": math.hypot(u, v), "from": _dir(u, v)},
            *rows,
        ]
    return out


def compare(cache: Path, arl_dir: str, arl: str) -> dict[str, Any]:
    """Return matched-time rows: forecast, analysis and forecast minus analysis."""
    fc, an = forecast(cache), analysis(arl_dir, arl)
    out: dict[str, Any] = {}
    for hour in sorted(set(fc) & set(an)):
        a = {r["level"]: r for r in an[hour]}
        rows = []
        for f in fc[hour]:
            r: dict[str, Any] = {"level": f["level"], "forecast": f, "analysis": a.get(f["level"])}
            if r["analysis"]:
                r["dir_error"] = (f["from"] - r["analysis"]["from"] + 180) % 360 - 180
                r["speed_error_ms"] = f["ms"] - r["analysis"]["ms"]
            rows.append(r)
        out[str(hour)] = rows
    return out


if __name__ == "__main__":
    json.dump(compare(Path(sys.argv[1]), sys.argv[2], sys.argv[3]), sys.stdout, indent=1)
    sys.stdout.write("\n")
