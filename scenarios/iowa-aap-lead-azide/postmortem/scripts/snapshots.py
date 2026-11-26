"""The cloud at the Army map's time marks: snapshots from the tracker and HYSPLIT.

Usage (from the repository root, ``HYSPLIT_DIR`` set)::

    python snapshots.py FORECAST_CACHE ANALYSIS_CACHE HYSPLIT_ARCHIVE HYSPLIT_PRESSURE > out.json

The Army's final air map marks the cloud 0.5, 2, 3 and 5 hours after the detonation.
For each time this gives each model's cloud at that moment for the 26% case: where air
at the ground is 0.18 µg/m³ or more (nearest and farthest distance, area) and the
air-weighted center.

- Tracker: the model is rerun here (HRRR only, the site's settings) on the saved forecast
  (FORECAST_CACHE, ``met_cache/map_met_all.json`` at the 9 a.m. commit) and on the saved
  analyzed weather (ANALYSIS_CACHE). The map pages keep a snapshot only on the hour; this
  script takes the model's own time steps and grids the one that ends at each mark, so it
  also covers the half hour.
- HYSPLIT: the 0-10 m snapshot grid (``csnap``, every 30 minutes) of the run on NOAA ARL's
  archived weather and of the run on the pressure-level analyses, for the times each
  covers.
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

import lib
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
import puff_dispersal  # noqa: E402
from dispersal import grid as dgrid  # noqa: E402

MARKS = (0.5, 2.0, 3.0, 5.0)  # hours after the detonation
SCALE = 0.26
MODEL_ARGS = [
    *("--lat", "40.825518", "--lon", "-91.266502", "--time", "2026-11-25T09:00-06:00"),
    *("--material", "lead-azide", "--explosive-mass", "9700lb", "--specific-energy", "1.64"),
    *("--shots", "2", "--confinement", "earth-covered", "--land-use", "crops"),
    *("--spread", "turbulence", "--hours", "8", "--dt", "60", "--grid", "360"),
    *("--scale-min", "0.15ug", "--decades", "4", "--weather-model", "ncep_hrrr_conus"),
    *("--release-case", "army-26"),
]


def describe(f: lib.Fields, field: np.ndarray) -> dict[str, float]:
    """Return the 0.18 µg/m³ extent and the air-weighted center of a snapshot."""
    return lib.zone(f, field, lib.ARMY_AIR) | lib.center(f, field)


Snaps = dict[str, tuple[lib.Fields, np.ndarray]]


def tracker_snaps(cache: Path) -> Snaps:
    """Rerun the tracker on a saved weather file and grid its time step at each mark."""
    as_of = max(json.loads(cache.read_text())["__fetched__"].values())  # replay as pulled
    seen: dict[str, Any] = {}
    original = puff_dispersal.grid_fields

    def spy(records: Any, n_hours: int, n_cells: int, dt_s: float, *rest: Any, **kw: Any) -> Any:  # noqa: ANN401
        out = original(records, n_hours, n_cells, dt_s, *rest, **kw)
        seen.setdefault("run", (records, out[1], dt_s))  # the first call is the shown run
        return out

    puff_dispersal.grid_fields = spy
    os.environ["PUFF_MET_CACHE_ONLY"] = "1"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            args = [*MODEL_ARGS, "--met-cache", str(cache), "--as-of", as_of]
            args += ["-o", f"{tmp}/map.html"]
            with Path(os.devnull).open("w") as quiet:
                puff_dispersal.simulate(puff_dispersal.parse_args(args), log=quiet)
    finally:
        puff_dispersal.grid_fields = original
    records, (xe, ye, dx), dt = seen["run"]
    steps = [r for r in records if np.any(r[4])]  # one air record per time step
    x = 0.5 * (xe[:-1] + xe[1:])
    y = 0.5 * (ye[:-1] + ye[1:])[::-1]  # south to north
    lat = lib.LAT0 + y / (lib.KM_PER_DEG * 1000)
    lon = lib.LON0 + x / (lib.KM_PER_DEG * 1000 * math.cos(math.radians(lib.LAT0)))
    cell = np.full(len(lat), (dx / 1000 / lib.KM_PER_MI) ** 2)
    out: Snaps = {}
    for mark in MARKS:
        step = steps[round(mark * 3600 / dt) - 1]
        scratch = np.zeros((len(ye) - 1, len(xe) - 1))
        air, _ = dgrid._accumulate_step(xe, ye, step, scratch, scratch.copy(), counts=False)  # noqa: SLF001
        f = lib.Fields(lat=lat, lon=lon, air={}, dep={}, snap={}, cell_mi2=cell, released_kg=0.0)
        out[f"{mark:g}"] = (f, air[::-1] / dt)
    return out


def lines_in(run: Path) -> int:
    """Return the number of starting locations in a run's CONTROL (two per line source)."""
    return int((run / "CONTROL").read_text().split("\n")[1])


def hysplit_snaps(run: Path) -> Snaps:
    """Read a HYSPLIT run's snapshot grid (csnap) at the marks it covers."""
    base = lib.hysplit(run, SCALE)  # for the grid geometry
    for f in run.glob("csnap_*"):
        f.unlink()
    exe = Path(os.environ["HYSPLIT_DIR"]) / "exec" / "con2asc"
    cmd = [str(exe), "-icsnap", "-ocsnap", "-d", "-x", "-t"]
    subprocess.run(cmd, cwd=run, check=True, capture_output=True)  # noqa: S603
    dx = base.lat[1] - base.lat[0]
    out: Snaps = {}
    for f in sorted(run.glob("csnap_*")):
        hhmm = f.name.split("_")[-1]  # csnap_DDD_HHMM
        mark = int(hhmm[:2]) + int(hhmm[2:]) / 60 - lib.RELEASE_HOUR_UTC
        if mark not in MARKS:
            continue
        rows = f.read_text().splitlines()
        head = [c.strip() for c in rows[0].split(",")]
        v = np.array([[float(x) for x in row.split(",")] for row in rows[1:]]).reshape(
            -1, len(head)
        )
        cols = [k for k, c in enumerate(head) if c.startswith("P0")]
        lat_i, lon_i = head.index("LAT"), head.index("LON")
        air = np.zeros((len(base.lat), len(base.lon)))
        j = np.rint((v[:, lat_i] - base.lat[0]) / dx).astype(int)
        k = np.rint((v[:, lon_i] - base.lon[0]) / dx).astype(int)
        air[j, k] = v[:, cols].sum(1) * SCALE * 2 / lines_in(run)
        out[f"{mark:g}"] = (base, air)
    return out


def main(args: list[str]) -> None:
    """Build and print the JSON."""
    fc_cache, an_cache, hy_archive, hy_pressure = (Path(a) for a in args)
    runs = {
        "tracker forecast": tracker_snaps(fc_cache),
        "tracker analysis": tracker_snaps(an_cache),
        "hysplit archive": hysplit_snaps(hy_archive),
        "hysplit pressure levels": hysplit_snaps(hy_pressure),
    }
    out: dict[str, Any] = {"marks_hours": list(MARKS)}
    for name, snaps in runs.items():
        out[name] = {mark: describe(f, field) for mark, (f, field) in snaps.items()}
    json.dump(out, sys.stdout, indent=1)
    sys.stdout.write("\n")


if __name__ == "__main__":
    with lib.nominal_origin():  # distances along the path; the runs from the nominal point
        main(sys.argv[1:])
