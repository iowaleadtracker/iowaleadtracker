"""Zone sizes, reaches and cloud path from built tracker map pages, as JSON.

Usage (from the repository root)::

    python scenarios/iowa-aap-lead-azide/postmortem/scripts/tracker_stats.py MAP.html...

Distances in miles, areas in square miles, air in µg/m³. "Cloud center" is the
air-weighted center of each hour's mean ground-level air, the same measure
hysplit_stats.py uses for HYSPLIT.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import forecast_summary as fs

KM_PER_MI = 1.609344
KM2_PER_MI2 = KM_PER_MI**2
KG_PER_LB = 0.45359237
ARMY_AIR_KG_M3 = 0.18e-9  # the Army map's air line, 0.18 µg/m³


def cell_centers(g: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    """Return 2-D latitude and longitude of the map's cell centers."""
    lon = g["west"] + (np.arange(g["nx"]) + 0.5) / g["nx"] * (g["east"] - g["west"])
    lat = g["north"] - (np.arange(g["ny"]) + 0.5) / g["ny"] * (g["north"] - g["south"])
    lo, la = np.meshgrid(lon, lat)
    return la, lo


def stats(path: Path) -> dict[str, Any]:
    """Return the postmortem numbers for one map page."""
    d = fs.load_map(path)
    m, g = d["meta"], d["grid"]
    dep = fs.field(d, "dep")[-1]
    m60 = fs.field(d, "m60")
    la, lo = cell_centers(g)
    r: dict[str, Any] = {
        "shown": (m.get("ensemble") or {}).get("shown"),
        "lead_lb": m["releaseMass"] / KG_PER_LB,
        "deposited_lb": d["hours"][-1]["dry"] / KG_PER_LB,
        "grid_km": g["dx"] / 1000,
    }
    for ug in (100, 40, 5):
        km, area = fs.zone_stats(d, dep, ug * fs.KG_M2_PER_UG_FT2)
        r[f"dep{ug}"] = {"reach_mi": km / KM_PER_MI, "area_mi2": area / KM2_PER_MI2}
    mask = dep >= 5 * fs.KG_M2_PER_UG_FT2
    if mask.any():
        far = max(
            fs.dist_bearing(m["lat"], m["lon"], a, b)
            for a, b in zip(la[mask], lo[mask], strict=True)
        )
        r["dep5_far_bearing"] = far[1]
    r["air_peak_ugm3"] = float(np.max(m60)) * 1e9
    r["pac1_reach_mi"] = fs.zone_stats(d, m60.max(axis=0), fs.PAC1_KG_M3)[0] / KM_PER_MI
    hours = []
    for k, h in enumerate(d["hours"]):
        a = m60[k]
        km, area = fs.zone_stats(d, a, ARMY_AIR_KG_M3)
        w = a / a.sum()
        dist, brg = fs.dist_bearing(
            m["lat"], m["lon"], float((w * la).sum()), float((w * lo).sum())
        )
        hours.append(
            {
                "h": k + 1,
                "t": h["t"],
                "wind_ms": h["ws"],
                "wind_from": h["wd"],
                "stability": h.get("stab"),
                "mixing_height_m": h.get("blh"),
                "sunshine_wm2": h.get("sw"),
                "peak_ugm3": float(np.max(a)) * 1e9,
                "air018_reach_mi": km / KM_PER_MI,
                "air018_area_mi2": area / KM2_PER_MI2,
                "center_mi": dist / KM_PER_MI,
                "center_bearing": brg,
            }
        )
    r["hours"] = hours
    return r


def main() -> None:
    """Print the numbers for every map named on the command line."""
    out = {Path(p).name: stats(Path(p)) for p in sys.argv[1:]}
    json.dump(out, sys.stdout, indent=1)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
