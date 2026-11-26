"""Could EPA's monitors have seen a cloud? Model air at every EPA site, by cloud direction.

Usage (from the repository root, ``HYSPLIT_DIR`` set)::

    python monitor_coverage.py FORECAST_MAPS ANALYSIS_MAPS HYSPLIT_RUN EPA_DIR HYSPLIT_LOFTED \
        > coverage.json

HYSPLIT_LOFTED is a 4-hour HYSPLIT run with the cloud released between the modeled cloud
top (251 m) and twice that height, the open-air value of the cloud-rise formula
(``blast-day/2026-11-25-9am-zhang-lofted.CONTROL``). It tests a cloud that started above
the morning mixed layer.

For each model run (with all of the lead airborne; other releases scale in proportion):

- the highest hourly mean air at each of EPA's 43 sampling sites, and the smallest share of
  the lead that would put an hourly mean at or above two levels there: 0.18 µg/m³ (the
  Army map's "detection limit" line) and 0.01 µg/m³ (the highest reading the real-time
  monitors posted, before or after the detonation);
- a direction sweep: the modeled cloud is turned about the plant in 1° steps and the four
  real-time monitors are sampled again, giving the highest hourly mean any of them would
  read for each cloud direction. Turning the cloud rigidly ignores how its shape would
  change with a different wind, so this is a sensitivity test, not a forecast;
- a source-shift test: every distance and bearing here is from one point taken for the
  whole plant, and the site of the detonation is not public. The modeled cloud is moved,
  without turning it, so that it starts 1, 2 and 3 km from that point in each of 24
  directions, and the real-time monitors are sampled again. Moving the cloud rigidly
  ignores how the wind differs a few kilometers away, so this too is a sensitivity test;
- a 1% case: the ground zones, the lead on the ground and the reach of hourly air at or
  above 0.18 µg/m³ if 1% of the lead became airborne (the 100% run scaled, which is exact).
"""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

import lib
import numpy as np

LEVELS = {"army_line_0.18": 0.18e-9, "highest_reading_0.01": 0.01e-9}  # kg/m3
SWEEP = range(-30, 31)
SMALL_CASE = 0.01  # a release of 1% of the lead
SHIFT_KM = (1.0, 2.0, 3.0)  # how far the true source might be from the assumed point
SHIFT_DIRECTIONS = range(0, 360, 15)
LOW_CASE = 0.07  # the lowest published release
DEP_LEVELS = (100, 40, 5)  # µg/ft²
XACT = ("AS01", "AS02", "AS03", "AS04")


def worst_hour(f: lib.Fields) -> np.ndarray:
    """Return the highest hourly mean air in each cell over the run."""
    return np.max(np.stack([f.air[h] for h in sorted(f.air)]), axis=0)


def sample(f: lib.Fields, field: np.ndarray, miles: float, bearing: float) -> float:
    """Return the field at a distance and bearing from the plant (nearest cell)."""
    d = miles * lib.KM_PER_MI
    lat = lib.LAT0 + d * math.cos(math.radians(bearing)) / lib.KM_PER_DEG
    lon = lib.LON0 + d * math.sin(math.radians(bearing)) / (
        lib.KM_PER_DEG * math.cos(math.radians(lib.LAT0))
    )
    j = round((lat - f.lat[0]) / (f.lat[1] - f.lat[0]))
    i = round((lon - f.lon[0]) / (f.lon[1] - f.lon[0]))
    if 0 <= j < len(f.lat) and 0 <= i < len(f.lon):
        return float(field[j, i])
    return 0.0


def shifted(f: lib.Fields, field: np.ndarray, s: dict[str, Any], km: float, toward: float) -> float:
    """Return the field at a site when the source sits ``km`` away in direction ``toward``."""
    north = s["miles"] * lib.KM_PER_MI * math.cos(math.radians(s["bearing"]))
    east = s["miles"] * lib.KM_PER_MI * math.sin(math.radians(s["bearing"]))
    north -= km * math.cos(math.radians(toward))  # the site as seen from the moved source
    east -= km * math.sin(math.radians(toward))
    bearing = math.degrees(math.atan2(east, north)) % 360
    return sample(f, field, math.hypot(north, east) / lib.KM_PER_MI, bearing)


def source_shift(f: lib.Fields, field: np.ndarray, monitors: list[dict[str, Any]]) -> list[Any]:
    """Return what the real-time monitors read for each assumed error in the source point."""
    out = []
    for km in SHIFT_KM:
        best, nearest = [], []
        for toward in SHIFT_DIRECTIONS:
            reads = {m["site"]: shifted(f, field, m, km, toward) * 1e9 for m in monitors}
            best.append(max(reads.values()))
            nearest.append(reads[XACT[0]])
        out.append(
            {
                "shift_km": km,
                "directions": len(best),
                "nearest_monitor_100pct_ugm3": {"lowest": min(nearest), "highest": max(nearest)},
                "best_monitor_100pct_ugm3": {"lowest": min(best), "highest": max(best)},
                "directions_caught": {
                    f"{share:g}": sum(b * share >= LEVELS["army_line_0.18"] * 1e9 for b in best)
                    for share in (LOW_CASE, SMALL_CASE)
                },
                "missed_toward": {
                    f"{share:g}": [
                        t
                        for t, b in zip(SHIFT_DIRECTIONS, best, strict=True)
                        if b * share < LEVELS["army_line_0.18"] * 1e9
                    ]
                    for share in (LOW_CASE, SMALL_CASE)
                },
            }
        )
    return out


def sites(epa: Path) -> list[dict[str, Any]]:
    """Return EPA's sampling sites; the four real-time monitors are flagged."""
    out = []
    with (epa / "epa_air_stations.csv").open() as f:
        for r in csv.DictReader(f):
            name = r["station_id"].replace("-", "")
            lat, lon = float(r["lat"]), float(r["lon"])
            d, b = lib.dist_brg(lat, lon)
            out.append(
                {
                    "site": name,
                    "instruments": r["instruments"],
                    "miles": float(d),
                    "bearing": float(b),
                    "real_time_lead": name in XACT,
                }
            )
    return out


def main(args: list[str]) -> None:
    """Build and print the JSON."""
    fc_dir, an_dir, hy_run, epa, hy_lofted = (Path(a) for a in args)
    runs = {
        "tracker forecast": lib.tracker(fc_dir / "permit-0900.html"),
        "tracker analysis": lib.tracker(an_dir / "an_permit.html"),
        "hysplit analysis": lib.hysplit(hy_run),
        "hysplit lofted": lib.hysplit(hy_lofted),
    }
    all_sites = sites(epa)
    out: dict[str, Any] = {"levels_ugm3": {k: v * 1e9 for k, v in LEVELS.items()}, "runs": {}}
    for name, f in runs.items():
        field = worst_hour(f)
        axis = lib.center(f, f.air[1])["center_bearing"]
        rows = []
        for s in all_sites:
            c = sample(f, field, s["miles"], s["bearing"])
            row = {**s, "air_100pct_ugm3": c * 1e9}
            for key, level in LEVELS.items():
                row[f"smallest_share_{key}"] = level / c if c else None
            rows.append(row)
        sweep = []
        for turn in SWEEP:
            reads = {
                s["site"]: sample(f, field, s["miles"], s["bearing"] - turn) * 1e9
                for s in all_sites
                if s["real_time_lead"]
            }
            best = max(reads, key=lambda k: reads[k])
            sweep.append(
                {
                    "cloud_bearing": axis + turn,
                    "best_monitor": best,
                    "air_100pct_ugm3": reads[best],
                    "by_monitor": reads,
                }
            )
        last = max(f.dep)
        small = {
            "share": SMALL_CASE,
            "released_lb": f.released_kg * SMALL_CASE / lib.KG_PER_LB,
            "deposited_lb": lib.deposited_lb(f, last) * SMALL_CASE,
            "dep": {
                str(u): lib.zone(f, f.dep[last] * SMALL_CASE, u * lib.UG_FT2) for u in DEP_LEVELS
            },
            "air_army_line": lib.zone(f, field * SMALL_CASE, lib.ARMY_AIR),
            "air_pac1": lib.zone(f, field * SMALL_CASE, lib.PAC1),
        }
        out["runs"][name] = {
            "cloud_bearing_hour1": axis,
            "sites": rows,
            "sweep": sweep,
            "case_1pct": small,
            "source_shift": source_shift(f, field, [s for s in all_sites if s["real_time_lead"]]),
        }
    json.dump(out, sys.stdout, indent=1)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main(sys.argv[1:])
