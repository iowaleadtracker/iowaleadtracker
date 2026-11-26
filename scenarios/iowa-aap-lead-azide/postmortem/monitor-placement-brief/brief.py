"""Redraw the monitor-placement map and recompute every number in this folder's README.

Usage (from anywhere; needs the network for the aerial imagery only)::

    python scenarios/iowa-aap-lead-azide/postmortem/monitor-placement-brief/brief.py

Reads, all from ``data/`` (see ``data/README.md``): the three modeled fields the map is
drawn from, EPA's public site list and real-time readings, where the release is modeled
from, and the Army's final ground map with where it sits on the ground.

Writes ``monitor_placement_map.png`` (and a smaller ``.jpg`` copy for the site's page) and
``numbers.json``, and rewrites the tables between
the ``<!-- table:NAME -->`` markers in ``README.md``. Pass ``--no-map`` to skip the map
(then no network is needed).
"""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

import brief_lib as lib
import brief_map
import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates

HERE = Path(__file__).resolve().parent
RELEASE_UTC = "2026-11-25 15:00"
XACT = ("AS01", "AS02", "AS03", "AS04")
FILTER = ("AS06", "AS12", "AS13")
RUNS = {
    "forecast": "Tracker, forecast",
    "analysis": "Tracker, analyzed weather",
    "hysplit": "HYSPLIT, archived weather",
}
RINGS_MI = (5, 10, 20)
PIXEL_MI = 0.6  # one pixel of the Army's map
UG = lib.UG
SMALL = 0.001


def nearest(grid: lib.Grid, lat: float, lon: float) -> float:
    """Return a field's value in the cell nearest a point (0 outside the saved area)."""
    glon, glat, air = grid
    j = round((lat - glat[0]) / (glat[1] - glat[0]))
    i = round((lon - glon[0]) / (glon[1] - glon[0]))
    return float(air[j, i]) if 0 <= j < len(glat) and 0 <= i < len(glon) else 0.0


def ring_peak(grid: lib.Grid, miles: float) -> float | None:
    """Return the bearing from the source at which a field is highest, at a distance."""
    glon, glat, air = grid
    brg = np.arange(150.0, 300.0, 0.25)
    d = miles * lib.KM_PER_MI
    lat = lib.LAT0 + d * np.cos(np.radians(brg)) / lib.KM_PER_DEG
    lon = lib.LON0 + d * np.sin(np.radians(brg)) / (
        lib.KM_PER_DEG * math.cos(math.radians(lib.LAT0))
    )
    rows = (lat - glat[0]) / (glat[1] - glat[0])
    cols = (lon - glon[0]) / (glon[1] - glon[0])
    v = map_coordinates(gaussian_filter(air, 1.0), [rows, cols], order=1, cval=0.0)
    return float(brg[int(np.argmax(v))]) if v.max() >= lib.ARMY_AIR else None


def on_army_map(lat: float, lon: float) -> dict[str, Any]:
    """Say where a point falls on the Army's final ground map.

    Returns the miles to the nearest traced pixel of the 5 µg/ft² zone, and whether the
    point is under the magenta plant marker, which hides whatever the map shows there.
    """
    ref = lib.army_placement()
    zones = lib.army_zones()
    x, y = (float(v) for v in lib.to_pixel(ref, np.array(lon), np.array(lat)))
    ys, xs = np.nonzero(zones["dep5"])
    px_per_mi = ref["k"] / (lib.KM_PER_DEG * math.cos(math.radians(lat)) / lib.KM_PER_MI)
    return {
        "miles_to_zone": float(np.hypot(xs - x, ys - y).min() / px_per_mi),
        "under_marker": bool(zones["marker"][round(y), round(x)]),
    }


def sites() -> dict[str, dict[str, Any]]:
    """Return EPA's sites of interest with distance and bearing from the modeled source."""
    out = {}
    with (HERE / "data/epa/epa_air_stations.csv").open() as fh:
        for r in csv.DictReader(fh):
            name = r["station_id"].replace("-", "")
            if name in XACT + FILTER:
                la, lo = float(r["lat"]), float(r["lon"])
                d, b = lib.dist_brg(la, lo)
                out[name] = {"lat": la, "lon": lo, "miles": float(d), "bearing": float(b)}
    return dict(sorted(out.items()))


def in_rerun_path(grids: dict[str, lib.Grid]) -> dict[str, dict[str, Any]]:
    """Return EPA's sites where either rerun on analyzed weather reaches the Army's air line.

    Covers the saved area only, about 30 miles from the source. Values are for the 7% case.
    """
    found: list[tuple[float, str, dict[str, Any]]] = []
    with (HERE / "data/epa/epa_air_stations.csv").open() as fh:
        for r in csv.DictReader(fh):
            la, lo = float(r["lat"]), float(r["lon"])
            air = {k: nearest(grids[k], la, lo) * UG for k in ("analysis", "hysplit")}
            if max(air.values()) >= lib.ARMY_AIR * UG:
                d, b = lib.dist_brg(la, lo)
                site = {
                    "miles": float(d),
                    "bearing": float(b),
                    "air_ugm3": air,
                    "instruments": r["instruments"],
                }
                found.append((float(d), r["station_id"].replace("-", ""), site))
    return {name: site for _, name, site in sorted(found, key=lambda f: f[0])}


def readings() -> dict[str, dict[str, Any]]:
    """Summarize EPA's posted real-time readings, by station, from the detonation on."""
    with (HERE / "data/epa/epa_xact_public_viewer.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    out: dict[str, dict[str, Any]] = {}
    for name in (*XACT, "all"):
        mine = [r for r in rows if name in ("all", r["station_id"])]
        after = [float(r["concentration"]) for r in mine if r["time_utc"] >= RELEASE_UTC]
        before = [float(r["concentration"]) for r in mine if r["time_utc"] < RELEASE_UTC]
        out[name] = {
            "posted": len(after),
            "zero": sum(v == 0 for v in after),
            "highest": max(after),
            "highest_before": max(before, default=0.0),
            "last_utc": max(r["time_utc"] for r in mine),
        }
    return out


def numbers(grids: dict[str, lib.Grid]) -> dict[str, Any]:
    """Compute everything the README quotes."""
    out: dict[str, Any] = {
        "source": {"lat": lib.LAT0, "lon": lib.LON0, "magazines": lib.source_coordinates()},
        "sites": sites(),
        "paths": {k: {str(m): ring_peak(g, m) for m in RINGS_MI} for k, g in grids.items()},
        "in_rerun_path": in_rerun_path(grids),
        "readings": readings(),
        "army_map": lib.army_placement(),
    }
    for s in out["sites"].values():
        s["air_ugm3"] = {k: nearest(g, s["lat"], s["lon"]) * UG for k, g in grids.items()}
        s["army_map"] = on_army_map(s["lat"], s["lon"])
    return out


def num(x: float) -> str:
    """Format a value to two significant figures; below 0.001 µg/m³ is shown as 0."""
    if x >= 10:
        return f"{x:.0f}"
    if x >= 1:
        return f"{x:.1f}"
    return f"{x:.2g}" if x >= SMALL else "0"


def tables(n: dict[str, Any]) -> dict[str, str]:
    """Build the README's tables."""
    head = "| Site | Kind | From the modeled source | " + " | ".join(RUNS.values())
    rows = [head + " | On the Army's ground map |", "|---" * (len(RUNS) + 4) + "|"]
    for name, s in n["sites"].items():
        kind = "real-time lead monitor" if name in XACT else "filter sampler, no results posted"
        gap = s["army_map"]["miles_to_zone"]
        zone = "in the zone" if gap <= PIXEL_MI / 2 else f"{gap:.1f} mi outside the zone"
        if s["army_map"]["under_marker"]:
            zone = "under the plant marker"
        air = " | ".join(num(s["air_ugm3"][k]) for k in RUNS)
        rows.append(
            f"| {name} | {kind} | {s['miles']:.1f} mi at {s['bearing']:.0f}° | {air} | {zone} |"
        )
    paths = ["| Run | " + " | ".join(f"{m} miles out" for m in RINGS_MI) + " |"]
    paths.append("|---" * (len(RINGS_MI) + 1) + "|")
    for k, label in RUNS.items():
        cells = [f"{b:.0f}°" if b is not None else "below 0.18" for b in n["paths"][k].values()]
        paths.append(f"| {label} | " + " | ".join(cells) + " |")
    near = []  # the real-time monitor nearest each distance
    for m in RINGS_MI:
        name, s = min(
            ((k, s) for k, s in n["sites"].items() if k in XACT),
            key=lambda ks: abs(ks[1]["miles"] - m),
        )
        near.append(f"{s['bearing']:.0f}° ({name}, {s['miles']:.1f} mi)")
    paths.append("| EPA's real-time monitor nearest that distance | " + " | ".join(near) + " |")
    read = ["| Monitor | Readings posted | Zero | Highest, µg/m³ | Highest before, µg/m³ |"]
    read.append("|---|---|---|---|---|")
    for name, r in n["readings"].items():
        label = "All four" if name == "all" else name
        read.append(
            f"| {label} | {r['posted']} | {r['zero']} | {r['highest']:.3f} | "
            f"{r['highest_before']:.3f} |"
        )
    head = (
        "| Site | From the modeled source | Tracker, analyzed weather | HYSPLIT, archived weather"
    )
    need = [head + " | Instruments EPA lists there | Results public |", "|---|---|---|---|---|---|"]
    for name, s in n["in_rerun_path"].items():
        air = " | ".join(num(s["air_ugm3"][k]) for k in ("analysis", "hysplit"))
        kit = s["instruments"].replace("Dust Trak", "DustTrak").replace("Cannister", "canister")
        if name in XACT:
            kit = "Xact real-time lead monitor, " + kit
        public = "real-time lead only" if name in XACT else "none"
        need.append(
            f"| {name} | {s['miles']:.1f} mi at {s['bearing']:.0f}° | {air} | {kit} | {public} |"
        )
    return {
        "sites": "\n".join(rows),
        "paths": "\n".join(paths),
        "readings": "\n".join(read),
        "needed": "\n".join(need),
    }


def main(args: list[str]) -> None:
    """Recompute the numbers, rewrite the README's tables and redraw the map."""
    grids = lib.load_fields()
    n = numbers(grids)
    (HERE / "numbers.json").write_text(json.dumps(n, indent=1) + "\n")
    path = HERE / "README.md"
    text = path.read_text()
    for name, body in tables(n).items():
        start, end = f"<!-- table:{name} -->\n", f"\n<!-- /table:{name} -->"
        i = text.index(start) + len(start)
        text = text[:i] + body + text[text.index(end, i) :]
    path.write_text(text)
    if "--no-map" not in args:
        brief_map.draw(grids, HERE / "monitor_placement_map.png")


if __name__ == "__main__":
    main(sys.argv[1:])
