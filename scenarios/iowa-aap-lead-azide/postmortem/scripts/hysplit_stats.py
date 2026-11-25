"""Zone sizes, reaches and cloud path from a HYSPLIT run, as JSON.

Usage::

    HYSPLIT_DIR=/path/to/hysplit python hysplit_stats.py RUN_DIR RELEASE_HOUR_UTC SCALE...

RUN_DIR holds CONTROL and cdump. Scale 1.0 is the CONTROL's release (100% of the
lead); 0.26 is the Army's mitigated case. HYSPLIT's transport and deposition don't
depend on the amount released, so scaling is exact. Air is the 0-10 m layer; ground
lead is summed over the run's hourly deposition. Distances in miles, areas in
square miles.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np

LAT0, LON0 = 40.825518, -91.266502
KM_PER_DEG = 111.195
KM_PER_MI = 1.609344
KG_M2_PER_UG_FT2 = 1e-9 / 0.09290304
KG_PER_LB = 0.45359237
ARMY_AIR = 0.18e-9  # kg/m3
PAC1 = 32e-9  # kg/m3, DOE PAC-1 for lead


def grid_spacing(run: Path) -> float:
    """Return the concentration grid spacing (degrees) from the run's CONTROL."""
    lines = (run / "CONTROL").read_text().split("\n")
    i = next(k for k, line in enumerate(lines) if line.strip() == "cdump")
    return float(lines[i - 3].split()[0])


def read_hours(
    run: Path, release_hour: int
) -> list[tuple[int, np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    """Dump cdump with con2asc; return (hour, lat, lon, air 0-10 m, deposition) per hour."""
    for f in run.glob("cdump_*"):
        f.unlink()
    exe = Path(os.environ["HYSPLIT_DIR"]) / "exec" / "con2asc"
    subprocess.run([str(exe), "-icdump", "-d", "-x"], cwd=run, check=True, capture_output=True)  # noqa: S603
    out = []
    for f in sorted(run.glob("cdump_*")):
        rows = f.read_text().splitlines()
        head = [c.strip() for c in rows[0].split(",")]
        v = np.array([[float(x) for x in row.split(",")] for row in rows[1:]]).reshape(
            -1, len(head)
        )
        i10 = [k for k, c in enumerate(head) if c.startswith("P0") and c.endswith("00010")]
        i0 = [k for k, c in enumerate(head) if c.startswith("P0") and c.endswith("00000")]
        out.append(
            (int(f.name[-2:]) - release_hour, v[:, 2], v[:, 3], v[:, i10].sum(1), v[:, i0].sum(1))
        )
    return out


def dist_brg(lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return distance (mi) and bearing (degrees from north) from the plant."""
    dy = (lat - LAT0) * KM_PER_DEG
    dx = (lon - LON0) * KM_PER_DEG * math.cos(math.radians(LAT0))
    return np.hypot(dx, dy) / KM_PER_MI, (np.degrees(np.arctan2(dx, dy)) + 360) % 360


def stats(run: Path, release_hour: int, scales: list[float]) -> dict[str, Any]:
    """Return the postmortem numbers for each release scale."""
    dx = grid_spacing(run)
    hours = read_hours(run, release_hour)
    dep: dict[tuple[float, float], float] = {}
    for _, lat, lon, _, d0 in hours:
        for a, b, x in zip(lat, lon, d0, strict=True):
            if x:
                key = (round(float(a), 4), round(float(b), 4))
                dep[key] = dep.get(key, 0.0) + float(x)
    k = np.array(list(dep), dtype=float).reshape(-1, 2)
    dv = np.array(list(dep.values()))
    cell_m2 = (dx * KM_PER_DEG * 1000) ** 2 * np.cos(np.radians(k[:, 0]))
    cell_mi2 = cell_m2 / 1e6 / KM_PER_MI**2
    out: dict[str, Any] = {}
    for s in scales:
        r: dict[str, Any] = {"deposited_lb": float((dv * s * cell_m2).sum() / KG_PER_LB)}
        for ug in (100, 40, 5):
            m = dv * s >= ug * KG_M2_PER_UG_FT2
            d, b = dist_brg(k[m, 0], k[m, 1])
            i = int(np.argmax(d)) if m.any() else 0
            r[f"dep{ug}"] = {
                "area_mi2": float(cell_mi2[m].sum()),
                "reach_mi": float(d[i]) if m.any() else 0.0,
                "far_brg": float(b[i]) if m.any() else 0.0,
            }
        rows = []
        for h, lat, lon, air, _ in hours:
            a = air * s
            dd, _ = dist_brg(lat, lon)
            w = a / a.sum()
            cd, cb = dist_brg(np.array([(w * lat).sum()]), np.array([(w * lon).sum()]))
            m = a >= ARMY_AIR
            p = a >= PAC1
            cmi2 = (dx * KM_PER_DEG) ** 2 * np.cos(np.radians(lat[m])) / KM_PER_MI**2
            rows.append(
                {
                    "h": h,
                    "peak_ugm3": float(np.max(a)) * 1e9,
                    "air018_near_mi": float(np.min(dd[m])) if m.any() else 0.0,
                    "air018_reach_mi": float(np.max(dd[m])) if m.any() else 0.0,
                    "air018_area_mi2": float(cmi2.sum()),
                    "center_mi": float(cd[0]),
                    "center_bearing": float(cb[0]),
                    "pac1_reach_mi": float(np.max(dd[p])) if p.any() else 0.0,
                }
            )
        r["hours"] = rows
        out[str(s)] = r
    return out


def main() -> None:
    """Print the numbers for the run named on the command line."""
    run, hour, *scales = sys.argv[1:]
    json.dump(stats(Path(run), int(hour), [float(x) for x in scales]), sys.stdout, indent=1)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
