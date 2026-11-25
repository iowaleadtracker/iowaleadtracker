"""Every model number in the first comparison, as one JSON file.

Usage (from the repository root, ``HYSPLIT_DIR`` set)::

    python compare.py FORECAST_MAPS ANALYSIS_MAPS HYSPLIT_ZHANG HYSPLIT_EMERSON EPA_DIR > out.json

FORECAST_MAPS holds the site's maps rebuilt from the forecast it showed at 9 a.m.
(``low-0900.html``, ``mid-0900.html``, ``permit-0900.html``). ANALYSIS_MAPS holds the
tracker rerun on HRRR's analyzed hours (``an_low.html``, ``an_mid.html``,
``an_permit.html``) and the sensitivity runs (``an_mid_*.html``). The HYSPLIT run
directories are the runs on the hourly analyses. EPA_DIR holds ``epa_fetch.py`` output.
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
                    "miles": float(r["miles_from_plant"]),
                    "bearing": float(r["bearing_from_plant"]),
                    "readings": [],
                },
            )
            s["readings"].append((r["time_utc"], float(r["concentration"])))
    for s in out.values():
        after = [v for t, v in s["readings"] if t[11:] >= "15:00"]
        before = [v for t, v in s["readings"] if t[11:] < "15:00"]
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


def main(args: list[str]) -> None:
    """Build and print the JSON."""
    fc_dir, an_dir, hz, he, epa = (Path(a) for a in args)
    stations = monitors(epa)
    hy = lib.hysplit(hz)
    hy_hours = sorted(hy.air)
    last = hy_hours[-1]
    out: dict[str, Any] = {
        "hysplit_hours": hy_hours,
        "epa_monitors": stations,
        "runs": {},
        "at_monitors": {},
    }
    fields: dict[str, lib.Fields] = {}
    for label, (case, scale) in CASES.items():
        fields[f"tracker forecast {label}"] = lib.tracker(fc_dir / f"{case}-0900.html")
        fields[f"tracker analysis {label}"] = lib.tracker(an_dir / f"an_{case}.html")
        fields[f"hysplit analysis {label}"] = lib.hysplit(hz, scale)
        fields[f"hysplit analysis emerson {label}"] = lib.hysplit(he, scale)
    for name, f in fields.items():
        hours = hy_hours if name.startswith("hysplit") else [1, 2, 3, 4, 8]
        out["runs"][name] = summary(f, hours)
        out["at_monitors"][name] = at_monitors(f, stations, hy_hours)
    out["overlap"] = {}
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
    out["sensitivity_26pct_8h"] = {}
    for name, file in SENSITIVITY.items():
        f = lib.tracker(an_dir / file)
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
    json.dump(out, sys.stdout, indent=1)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main(sys.argv[1:])
