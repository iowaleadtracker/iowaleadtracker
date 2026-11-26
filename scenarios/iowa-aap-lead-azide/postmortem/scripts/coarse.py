"""Air at EPA's nearest monitor if the lead came out as coarse particles.

Usage (from the repository root, ``HYSPLIT_DIR`` set)::

    python coarse.py ANALYSIS_CACHE EPA_DIR HYSPLIT_COARSE_RUN > coarse.json

The published cases put all airborne lead in fine sizes (0.3 to 10 µm). This reruns the
tracker on the saved analyzed weather with all of the lead airborne in one size at a
time: the four fine sizes at lead's density, 10, 30 and 100 µm at the density of soil
(the tracker's coarse sizes, lead carried on soil and debris) and 30 µm at lead's
density. For each size it gives the
settling speed, the highest hourly mean air at EPA's nearest real-time monitor (AS01) and
at the two filter sites on the surface-wind path (AS06, AS12), the highest value at
AS01's distance in any direction, the share of the lead that has reached the ground
within AS01's distance and within 15 miles, and the ground zones for the 26% case.

HYSPLIT_COARSE_RUN is a 2-hour HYSPLIT run on NOAA ARL's archived weather with the same
three coarse sizes (``blast-day/2026-11-25-9am-coarse-early2h.CONTROL``), each carrying
all of the lead, with the tracker's deposition speeds at its 5 m/s reference wind. It is
an independent check on the tracker's coarse sizes.
"""

from __future__ import annotations

import csv
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import lib
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from dispersal import deposition  # noqa: E402

LEAD, SOIL = 9500.0, 2650.0  # particle density, kg/m3
FINE = ((0.3, LEAD), (1.0, LEAD), (3.0, LEAD), (10.0, LEAD))
COARSE = ((10.0, SOIL), (30.0, SOIL), (100.0, SOIL), (30.0, LEAD))
SIZES = (*FINE, *COARSE)
CASE = 0.26  # share of the lead for the ground zones (the Army's emission factor)
HYSPLIT_SPECIES = {"P001": (10.0, SOIL), "P002": (30.0, SOIL), "P003": (100.0, SOIL)}
SITES = ("AS01", "AS06", "AS12")
NEAR_MI = 15.0
RING = np.arange(180.0, 270.0, 0.5)  # bearings searched for the highest value at a distance
MODEL_ARGS = [
    *("--lat", "40.825518", "--lon", "-91.266502", "--time", "2026-11-25T09:00-06:00"),
    *("--material", "lead-azide", "--explosive-mass", "9700lb", "--specific-energy", "1.64"),
    *("--shots", "2", "--confinement", "earth-covered", "--land-use", "crops"),
    *("--spread", "turbulence", "--hours", "8", "--dt", "60", "--grid", "360"),
    *("--scale-min", "0.15ug", "--decades", "4", "--weather-model", "ncep_hrrr_conus"),
    *("--airborne-fraction", "1.0"),
]


def sample(f: lib.Fields, field: np.ndarray, miles: float, bearing: float) -> float:
    """Return the field at a distance and bearing from the plant (nearest cell)."""
    d = miles * lib.KM_PER_MI
    lat = lib.LAT0 + d * math.cos(math.radians(bearing)) / lib.KM_PER_DEG
    lon = lib.LON0 + d * math.sin(math.radians(bearing)) / (
        lib.KM_PER_DEG * math.cos(math.radians(lib.LAT0))
    )
    return f.at(field, lat, lon)


def measures(f: lib.Fields, sites: dict[str, tuple[float, float]]) -> dict[str, Any]:
    """Return air at the sites and the share of the lead on the ground, for one size."""
    last = max(f.dep)
    worst = np.max(np.stack([f.air[h] for h in sorted(f.air)]), axis=0)
    la, lo = f.mesh()
    dist, _ = lib.dist_brg(la, lo)
    on_ground = f.dep[last] * f.cell_mi2[:, None] * (lib.KM_PER_MI * 1000) ** 2  # kg per cell
    as01_mi = float(lib.dist_brg(*sites["AS01"])[0])
    return {
        "hours": last,
        "air_100pct_ugm3": {n: f.at(worst, *sites[n]) * 1e9 for n in SITES},
        "ring_max_at_as01_distance_ugm3": max(sample(f, worst, as01_mi, b) for b in RING) * 1e9,
        "share_on_ground_within_as01_distance": float(on_ground[dist <= as01_mi].sum())
        / f.released_kg,
        "share_on_ground_within_15mi": float(on_ground[dist <= NEAR_MI].sum()) / f.released_kg,
        "share_on_ground": float(on_ground.sum()) / f.released_kg,
        "ground_zones_26pct": {
            str(u): lib.zone(f, f.dep[last] * CASE, u * lib.UG_FT2) for u in (100, 5)
        },
    }


def tracker_size(cache: Path, as_of: str, diameter_um: float, density: float) -> lib.Fields:
    """Run the tracker with all of the lead airborne in one particle size."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "map.html"
        args = [
            *MODEL_ARGS,
            "--particle-diameter",
            f"{diameter_um:g}um",
            "--density",
            f"{density:g}",
        ]
        args += ["--met-cache", str(cache), "--as-of", as_of, "-o", str(out)]
        env = {**os.environ, "PUFF_MET_CACHE_ONLY": "1"}
        cmd = [sys.executable, str(ROOT / "puff_dispersal.py"), *args]
        subprocess.run(cmd, cwd=ROOT, env=env, check=True, capture_output=True)  # noqa: S603
        return lib.tracker(out)


def settling_cm_s(diameter_um: float, density: float) -> float:
    """Return the tracker's terminal settling speed for a sphere, cm/s."""
    mass = density * math.pi * (diameter_um * 1e-6) ** 3 / 6.0
    return float(deposition.particle_properties(mass, density)[1]) * 100


def main(args: list[str]) -> None:
    """Build and print the JSON."""
    cache, epa, hy_run = (Path(a) for a in args)
    as_of = max(json.loads(cache.read_text())["__fetched__"].values())
    with (epa / "epa_air_stations.csv").open() as f:
        where = {
            r["station_id"].replace("-", ""): (float(r["lat"]), float(r["lon"]))
            for r in csv.DictReader(f)
        }
    sites = {n: where[n] for n in SITES}
    out: dict[str, Any] = {"sites_miles_bearing": {}, "tracker": [], "hysplit": []}
    for n, (la, lo) in sites.items():
        d, b = lib.dist_brg(la, lo)
        out["sites_miles_bearing"][n] = [float(d), float(b)]
    for diameter, density in SIZES:
        row = {"diameter_um": diameter, "density_kg_m3": density}
        row["settling_cm_s"] = settling_cm_s(diameter, density)
        out["tracker"].append(row | measures(tracker_size(cache, as_of, diameter, density), sites))
    for name, (diameter, density) in HYSPLIT_SPECIES.items():
        row = {"diameter_um": diameter, "density_kg_m3": density}
        out["hysplit"].append(row | measures(lib.hysplit(hy_run, species=name), sites))
    json.dump(out, sys.stdout, indent=1)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main(sys.argv[1:])
