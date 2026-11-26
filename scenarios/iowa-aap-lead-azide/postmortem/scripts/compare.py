"""Every model number in the first comparison, as one JSON file.

Usage (from the repository root, ``HYSPLIT_DIR`` set)::

    python compare.py FORECAST_MAPS ANALYSIS_MAPS HYSPLIT_ZHANG HYSPLIT_EMERSON \
        HYSPLIT_PRESSURE EPA_DIR SOURCES_ZHANG SOURCES_EMERSON SOURCES_PRESSURE > out.json

FORECAST_MAPS holds the site's maps rebuilt from the forecast it showed at 9 a.m.
(``low-0900.html``, ``mid-0900.html``, ``permit-0900.html``). ANALYSIS_MAPS holds the
tracker rerun on HRRR's analyzed hours (``an_low.html``, ``an_mid.html``,
``an_permit.html``) and the sensitivity runs (``an_mid_*.html``). HYSPLIT_ZHANG and
HYSPLIT_EMERSON are the run directories on NOAA ARL's archived HRRR (native levels), the
reference runs, keyed ``hysplit analysis``; HYSPLIT_PRESSURE is the run on the raw
pressure-level analyses, keyed ``hysplit pressure levels``. EPA_DIR holds ``epa_fetch.py``
output.

The model-with-model numbers (zones, overlap, centers, the sensitivity runs) don't depend
on where the source is, so they use the runs from the nominal point, unmoved. The values
at EPA's monitors do. They use the tracker's fields moved to the modeled sources
(``data/source.json``) and the SOURCES_* runs, which are the same HYSPLIT cases released
from those sources.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

import lib
import numpy as np

CASES = {"7%": ("low", 0.07), "26%": ("mid", 0.26), "100%": ("permit", 1.0)}
DEP_LEVELS = (100, 40, 5)
ARCS = ((1.5, 3), (3, 6), (6, 12), (12, 25))
NEAR_KM = 1.0
SENSITIVITY = {
    "baseline (fine sizes, Zhang)": "an_mid.html",
    "sizes 1-30 µm (mixed)": "an_mid_mixed.html",
    "sizes 10-100 µm (soil-bound)": "an_mid_soil.html",
    "half fine, half 30 and 100 µm": "an_mid_half.html",
    "fine sizes, deposition speed +1 cm/s": "an_mid_vd1.html",
    "fine sizes, Emerson deposition": "an_mid_emerson.html",
    "fine sizes, cloud top 151 m": "an_mid_low_cloud.html",
}
NEAR_FIELD_MI = 15
MONITOR_HOURS = 3
RELEASE_UTC = "2026-11-25 15:00"  # 9 a.m. CST, in the form of the readings' time stamps


def summary(f: lib.Fields, hours: list[int]) -> dict[str, Any]:
    """Return zones, deposition, air and cloud position for one model run."""
    out: dict[str, Any] = {"released_lb": f.released_kg / lib.KG_PER_LB, "hours": {}}
    for h in hours:
        air = f.air[h]
        row: dict[str, Any] = {
            "deposited_lb": lib.deposited_lb(f, h),
            "dep": {str(u): lib.zone(f, f.dep[h], u * lib.UG_FT2) for u in DEP_LEVELS},
            "air_peak_ugm3": float(air.max()) * 1e9,
            "air_arc_max_ugm3": {f"{a}-{b} mi": lib.arc_max(f, air, a, b) * 1e9 for a, b in ARCS},
            "air018": lib.zone(f, air, lib.ARMY_AIR),
            "pac1": lib.zone(f, air, lib.PAC1),
            "mean": lib.center(f, air),
        }
        if h in f.snap:
            row["snapshot"] = lib.center(f, f.snap[h]) | {
                "air018": lib.zone(f, f.snap[h], lib.ARMY_AIR)
            }
        out["hours"][str(h)] = row
    return out


def monitors(epa: Path) -> dict[str, dict[str, Any]]:
    """Return EPA's Xact stations with position and the readings' summary."""
    out: dict[str, dict[str, Any]] = {}
    with (epa / "epa_xact_public_viewer.csv").open() as f:
        for r in csv.DictReader(f):
            s = out.setdefault(
                r["station_id"],
                {
                    "lat": float(r["lat"]),
                    "lon": float(r["lon"]),
                    "miles": float(lib.dist_brg(float(r["lat"]), float(r["lon"]))[0]),
                    "bearing": float(lib.dist_brg(float(r["lat"]), float(r["lon"]))[1]),
                    "readings": [],
                },
            )
            s["readings"].append((r["time_utc"], float(r["concentration"])))
    for s in out.values():
        after = [v for t, v in s["readings"] if t >= RELEASE_UTC]  # full timestamps, so
        before = [v for t, v in s["readings"] if t < RELEASE_UTC]  # the next UTC day counts
        s["n_before"], s["n_after"] = len(before), len(after)
        s["max_before_ugm3"], s["max_after_ugm3"] = max(before), max(after)
        s["nonzero_after"] = sum(v > 0 for v in after)
        s["mean_after_ugm3"] = float(np.mean(after))
        s["last_reading_utc"] = s["readings"][-1][0]
        del s["readings"]
    return out


def at_monitors(
    f: lib.Fields, stations: dict[str, dict[str, Any]], hours: list[int]
) -> dict[str, Any]:
    """Return each model's hourly mean air (µg/m³) at the monitors and within 1 km."""
    out = {}
    for name, s in stations.items():
        out[name] = {
            str(h): {
                "at": f.at(f.air[h], s["lat"], s["lon"]) * 1e9,
                "within_1km": f.at(f.air[h], s["lat"], s["lon"], NEAR_KM) * 1e9,
            }
            for h in hours
        }
    return out


def load(
    maps: tuple[Path, Path], runs: tuple[Path, Path, Path], *, moved: bool
) -> dict[str, lib.Fields]:
    """Read every model run for every release case."""
    fc_dir, an_dir = maps
    hz, he, hp = runs
    fields: dict[str, lib.Fields] = {}
    for label, (case, scale) in CASES.items():
        fields[f"tracker forecast {label}"] = lib.tracker(fc_dir / f"{case}-0900.html", moved=moved)
        fields[f"tracker analysis {label}"] = lib.tracker(an_dir / f"an_{case}.html", moved=moved)
        fields[f"hysplit analysis {label}"] = lib.hysplit(hz, scale)
        fields[f"hysplit analysis emerson {label}"] = lib.hysplit(he, scale)
        fields[f"hysplit pressure levels {label}"] = lib.hysplit(hp, scale)
    return fields


def hours_of(name: str, f: lib.Fields) -> list[int]:
    """Return the hours summarized for a run."""
    return sorted(f.air) if name.startswith("hysplit") else [1, 2, 3, 4, 5, 8]


def model_comparison(maps: tuple[Path, Path], runs: tuple[Path, Path, Path]) -> dict[str, Any]:
    """Compare the models with each other, on the runs from the nominal point."""
    out: dict[str, Any] = {"runs": {}, "overlap": {}, "sensitivity_26pct_8h": {}}
    fields = load(maps, runs, moved=False)
    last = max(fields["hysplit analysis 26%"].air)
    out["hysplit_hours"] = sorted(fields["hysplit analysis 26%"].air)
    for name, f in fields.items():
        out["runs"][name] = summary(f, hours_of(name, f))
    for label in CASES:
        pairs = {
            "tracker forecast vs tracker analysis": ("tracker forecast", "tracker analysis"),
            "tracker analysis vs hysplit analysis": ("tracker analysis", "hysplit analysis"),
            "tracker forecast vs hysplit analysis": ("tracker forecast", "hysplit analysis"),
        }
        for pname, (a, b) in pairs.items():
            fa, fb = fields[f"{a} {label}"], fields[f"{b} {label}"]
            out["overlap"][f"{pname}, {label}, after {last} h"] = {
                str(u): lib.overlap(fa, fa.dep[last], fb, fb.dep[last], u * lib.UG_FT2)
                for u in DEP_LEVELS
            }
    for name, file in SENSITIVITY.items():
        f = lib.tracker(maps[1] / file, moved=False)
        la, lo = f.mesh()
        d, _ = lib.dist_brg(la, lo)
        near = float(
            (f.dep[8] * (d <= NEAR_FIELD_MI) * f.cell_mi2[:, None]).sum()
            * (lib.KM_PER_MI * 1000) ** 2
        )
        out["sensitivity_26pct_8h"][name] = {
            "dep": {str(u): lib.zone(f, f.dep[8], u * lib.UG_FT2) for u in DEP_LEVELS},
            "deposited_lb": lib.deposited_lb(f, 8),
            "deposited_within_15mi_lb": near / lib.KG_PER_LB,
        }
    return out


def main(args: list[str]) -> None:
    """Build and print the JSON."""
    paths = [Path(a) for a in args]
    maps = (paths[0], paths[1])
    nominal_runs = (paths[2], paths[3], paths[4])
    epa = paths[5]
    source_runs = (paths[6], paths[7], paths[8])
    with lib.nominal_origin():
        out = model_comparison(maps, nominal_runs)
    stations = monitors(epa)
    out["epa_monitors"] = stations
    out["at_monitors"] = {}
    for name, f in load(maps, source_runs, moved=True).items():
        hours = [h for h in hours_of(name, f) if h <= MONITOR_HOURS]
        out["at_monitors"][name] = at_monitors(f, stations, hours)
    json.dump(out, sys.stdout, indent=1)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main(sys.argv[1:])
