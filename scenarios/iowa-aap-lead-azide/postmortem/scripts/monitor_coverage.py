"""Could EPA's monitors have seen a cloud? Model air at every EPA site, by cloud direction.

Usage (from the repository root, ``HYSPLIT_DIR`` set)::

    python monitor_coverage.py FORECAST_MAPS ANALYSIS_MAPS HYSPLIT_RUN EPA_DIR > coverage.json

For each model run (with all of the lead airborne; other releases scale in proportion):

- the highest hourly mean air at each of EPA's 43 sampling sites, and the smallest share of
  the lead that would put an hourly mean at or above two levels there: 0.18 µg/m³ (the
  Army map's "detection limit" line) and 0.01 µg/m³ (the highest reading the real-time
  monitors posted, before or after the detonation);
- a direction sweep: the modeled cloud is turned about the plant in 1° steps and the four
  real-time monitors are sampled again, giving the highest hourly mean any of them would
  read for each cloud direction. Turning the cloud rigidly ignores how its shape would
  change with a different wind, so this is a sensitivity test, not a forecast.
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
    fc_dir, an_dir, hy_run, epa = (Path(a) for a in args)
    runs = {
        "tracker forecast": lib.tracker(fc_dir / "permit-0900.html"),
        "tracker analysis": lib.tracker(an_dir / "an_permit.html"),
        "hysplit analysis": lib.hysplit(hy_run),
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
        out["runs"][name] = {"cloud_bearing_hour1": axis, "sites": rows, "sweep": sweep}
    json.dump(out, sys.stdout, indent=1)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main(sys.argv[1:])
