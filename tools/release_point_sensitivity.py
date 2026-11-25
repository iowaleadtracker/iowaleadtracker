#!/usr/bin/env python3
"""Rerun the default map from release points moved around the plant, with the same weather.

The Army has not published where in the plant the lead azide magazines are, so the maps
start the cloud at one point for the plant (``make_map_picker.LAT, LON``). This tool asks
how much that choice matters: it reruns the default blast time from a ring of points
around that point and reports, for each, how far the 5, 40 and 100 ug/ft2 ground lines
reach, the area inside them, which listed towns are inside them, and the peak air level.

The weather is held fixed: forecasts are looked up for the published point (where the
saved forecasts are keyed), and only the release point moves. The ring is generic (3 km
in eight directions and 5 km in four); it is not based on the plant boundary or on where
any building is, so some points may lie outside the plant.

    python3 tools/release_point_sensitivity.py OUT_DIR [--cases permit-100,army-26]

Runs use the saved forecasts only (no downloads) and write ``OUT_DIR/<point>_<case>.html``
plus ``OUT_DIR/results.json``. About 30 s per run, four at a time.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "scenarios" / "iowa-aap-lead-azide"
sys.path[:0] = [str(ROOT), str(SCENARIO)]

import forecast_summary as fs  # noqa: E402
import make_map_picker as mmp  # noqa: E402

KM_PER_DEG_LAT = fs.KM_PER_DEG_LAT
RING = [(f"{d}3", 3.0, b) for d, b in zip(fs.COMPASS[::2], range(0, 360, 45), strict=True)]
RING += [(f"{d}5", 5.0, b) for d, b in zip(fs.COMPASS[::4], range(0, 360, 90), strict=True)]


def points() -> list[tuple[str, float, float]]:
    """Return (name, lat, lon) for the published point ("C") and the ring around it."""
    out = [("C", mmp.LAT, mmp.LON)]
    for name, km, bearing in RING:
        dy = km * math.cos(math.radians(bearing))
        dx = km * math.sin(math.radians(bearing))
        lat = mmp.LAT + dy / KM_PER_DEG_LAT
        lon = mmp.LON + dx / (KM_PER_DEG_LAT * math.cos(math.radians(mmp.LAT)))
        out.append((name, round(lat, 6), round(lon, 6)))
    return out


def model_args() -> list[str]:
    """Return the default map's model arguments, without --lat, --lon or -o."""
    pulled = mmp.retrieved_at()
    if pulled is None:
        raise SystemExit("no saved forecasts: run tools/refresh_forecast.py or build first")
    args = list(mmp.MODEL_ARGS) + mmp.temperature_args()
    args[args.index("--weather-model") + 1] = mmp.weather_for_day(mmp.DATE, pulled)
    return [
        *args,
        *("--time", f"{mmp.DATE}T{mmp.DEFAULT}-06:00"),
        *("--as-of", pulled.isoformat()),
        *mmp.sky_grid_args(),
    ]


def run_shifted(argv: list[str]) -> None:
    """Run puff_dispersal with ``argv``, but fetch weather for the published point."""
    import puff_dispersal as pd  # noqa: PLC0415

    build_met = pd.build_met

    def at_published_point(_lat: float, _lon: float, *a: Any, **kw: Any) -> Any:  # noqa: ANN401
        return build_met(mmp.LAT, mmp.LON, *a, **kw)

    pd.build_met = at_published_point  # type: ignore[assignment]
    pd.main(argv)


def summarize(path: Path) -> dict[str, Any]:
    """Return the ground-line reach and area, towns inside, and peak air for one map."""
    d = fs.load_map(path)
    dep = fs.field(d, "dep")[-1]
    out: dict[str, Any] = {}
    for key, ugft2 in fs.DEP_LEVELS:
        level = ugft2 * fs.KG_M2_PER_UG_FT2
        km, area = fs.zone_stats(d, dep, level)
        out[key] = {
            "reach_mi": round(km / fs.MI, 1),
            "area_sq_mi": round(area / fs.MI**2, 1),
            "towns": fs.towns_at_or_above(d, dep, level),
        }
    m60 = fs.field(d, "m60").max(axis=0)
    out["air_max_ug_m3"] = round(float(np.max(m60)) * 1e9, 1)
    out["pac1_reach_mi"] = round(fs.zone_stats(d, m60, fs.PAC1_KG_M3)[0] / fs.MI, 1)
    out["town_dep_ug_ft2"] = {}
    for name, lat, lon in fs.TOWNS:
        cell = fs.cell_of(d["grid"], lat, lon)
        if cell is not None and dep[cell] > 0:
            out["town_dep_ug_ft2"][name] = round(float(dep[cell]) / fs.KG_M2_PER_UG_FT2, 1)
    return out


def main(argv: list[str] | None = None) -> None:
    """Run every point and case, then print and save the comparison."""
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("out", type=Path, help="directory for the maps and results.json")
    p.add_argument("--cases", default="permit-100,army-26", help="release cases to run")
    p.add_argument("--run", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)
    a = p.parse_args(argv)
    if a.run is not None:  # one model run, in its own process
        run_shifted(a.run)
        return
    a.out.mkdir(parents=True, exist_ok=True)
    cases = [c.strip() for c in a.cases.split(",") if c.strip()]
    args = model_args()
    env = dict(os.environ, PUFF_MET_CACHE_ONLY="1", **mmp.ONE_THREAD)
    jobs = []
    for name, lat, lon in points():
        for case in cases:
            out = a.out / f"{name}_{case}.html"
            cmd = [sys.executable, __file__, str(a.out), "--run"]
            cmd += ["--lat", str(lat), "--lon", str(lon), "--release-case", case]
            jobs.append((name, case, out, [*cmd, *args, "-o", str(out)]))

    def run(job: tuple[str, str, Path, list[str]]) -> str:
        name, case, out, cmd = job
        if out.exists():
            return f"{name} {case}: kept"
        r = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False, cwd=ROOT)  # noqa: S603
        tail = r.stderr.strip().splitlines()[-1:] if r.returncode else []
        return f"{name} {case}: " + ("ok" if not r.returncode else f"FAILED {tail}")

    with ThreadPoolExecutor(mmp.PARALLEL_RUNS) as ex:
        for line in ex.map(run, jobs):
            print(line, flush=True)
    results = {
        case: {name: summarize(a.out / f"{name}_{case}.html") for name, _, _ in points()}
        for case in cases
    }
    (a.out / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    for case, rows in results.items():
        print(f"\n{case}, {mmp.DATE} {mmp.DEFAULT}")
        print("point  5 ug/ft2 mi  40 ug/ft2 mi  100 ug/ft2 mi  air max ug/m3  towns >= 5")
        for name, r in rows.items():
            print(
                f"{name:5} {r['yellow']['reach_mi']:>11} {r['orange']['reach_mi']:>13} "
                f"{r['red']['reach_mi']:>14} {r['air_max_ug_m3']:>14}  "
                + "; ".join(r["yellow"]["towns"])
            )


if __name__ == "__main__":
    main()
