"""Redraw the monitor-placement map and recompute every number in this folder's README.

Usage (from anywhere; needs the network for the aerial imagery only)::

    python scenarios/iowa-aap-lead-azide/postmortem/monitor-placement-brief/brief.py

Reads

- ``data/model_fields.npz``: the three modeled fields the map is drawn from (highest
  hourly mean lead in air at the ground, lowest published case, 7% airborne), saved by
  ``../scripts/aerial_map.py`` from the model runs;
- ``data/epa/``: EPA's public site list and real-time readings (``../scripts/epa_fetch.py``);
- ``../data/source.json``: where the release is modeled from;
- ``../data/army/`` and ``../data/army_georef.json``: the Army's final ground map and where
  it sits on the ground (``../scripts/georeference.py``).

Writes ``monitor_placement_map.png`` and ``numbers.json``, and rewrites the tables between
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

import numpy as np

HERE = Path(__file__).resolve().parent
POST = HERE.parent
sys.path.insert(0, str(POST / "scripts"))

import aerial_map  # noqa: E402
import army_map  # noqa: E402
import georeference  # noqa: E402
import lib  # noqa: E402
from matplotlib.colors import rgb_to_hsv  # noqa: E402
from PIL import Image  # noqa: E402
from scipy.ndimage import (  # noqa: E402
    binary_dilation,
    binary_fill_holes,
    gaussian_filter,
    map_coordinates,
)

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
MARKER_HUE, MARKER_SAT = (285, 340), 0.35  # the magenta plant marker on the Army's map
UG = 1e9  # kg/m³ to µg/m³
SMALL = 0.001


def nearest(grid: aerial_map.Grid, lat: float, lon: float) -> float:
    """Return a field's value in the cell nearest a point (0 outside the saved area)."""
    glon, glat, air = grid
    j = round((lat - glat[0]) / (glat[1] - glat[0]))
    i = round((lon - glon[0]) / (glon[1] - glon[0]))
    return float(air[j, i]) if 0 <= j < len(glat) and 0 <= i < len(glon) else 0.0


def ring_peak(grid: aerial_map.Grid, miles: float) -> float | None:
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
    ref = json.loads((POST / "data/army_georef.json").read_text())["ground"]
    path = army_map.image(POST / "data/army", "ground", "final")
    zone = army_map.masks(path, army_map.MAPS["final"]["tip"])["dep5"]
    hsv = rgb_to_hsv(np.asarray(Image.open(path).convert("RGB")).astype(float) / 255)
    magenta = (hsv[..., 0] * 360 > MARKER_HUE[0]) & (hsv[..., 0] * 360 < MARKER_HUE[1])
    marker = binary_fill_holes(binary_dilation(magenta & (hsv[..., 1] > MARKER_SAT)))
    x, y = (float(v) for v in georeference.to_pixel(ref, np.array(lon), np.array(lat)))
    ys, xs = np.nonzero(zone)
    px_per_mi = ref["k"] / (lib.KM_PER_DEG * math.cos(math.radians(lat)) / lib.KM_PER_MI)
    return {
        "miles_to_zone": float(np.hypot(xs - x, ys - y).min() / px_per_mi),
        "under_marker": bool(marker[round(y), round(x)]),
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


def in_rerun_path(grids: dict[str, aerial_map.Grid]) -> dict[str, dict[str, Any]]:
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


def numbers(grids: dict[str, aerial_map.Grid]) -> dict[str, Any]:
    """Compute everything the README quotes."""
    out: dict[str, Any] = {
        "source": {"lat": lib.LAT0, "lon": lib.LON0, "magazines": lib.source_coordinates()},
        "sites": sites(),
        "paths": {k: {str(m): ring_peak(g, m) for m in RINGS_MI} for k, g in grids.items()},
        "in_rerun_path": in_rerun_path(grids),
        "readings": readings(),
        "army_map": json.loads((POST / "data/army_georef.json").read_text())["ground"],
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
    by = [f"{s['miles']:.0f} mi: {s['bearing']:.0f}°" for k, s in n["sites"].items() if k in XACT]
    paths.append("| EPA's real-time monitors | " + ", ".join(by) + " | | |")
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
    grids = aerial_map.load_fields(HERE / "data/model_fields.npz")
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
        out = HERE / "monitor_placement_map.png"
        aerial_map.draw(grids, POST / "data/army", HERE / "data/epa", out)


if __name__ == "__main__":
    main(sys.argv[1:])
