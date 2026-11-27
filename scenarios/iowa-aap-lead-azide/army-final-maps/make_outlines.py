"""Trace the zones on the Army's final maps and save them as outlines for the site's maps.

Usage::

    python make_outlines.py            # trace, using the saved placement
    python make_outlines.py --place    # first place the air map again (needs the network)

The Army's final "Mitigated 0.26" maps (a/o 250700NOV26) are small pictures, about 0.6 mile
per pixel: an air map with the cloud's path shaded where lead in air would reach 0.18 µg/m³,
and a ground map with zones of 5 and 100 µg/ft². This script picks each shaded zone out of
its picture by color, closes the gaps left by the county names printed over it, and turns
its edge into lines of latitude and longitude, using where each picture sits on the ground
(fitted to its county lines by the brief's ``place_army_map.py``). The parts of an edge
under the Army's magenta plant marker are left out: the marker hides what is drawn there.

Writes ``outlines.json``, which ``make_map_picker.py`` hands to the maps
(``--reference-outlines``), and ``georef.json`` with ``--place``. The time lines the Army
labeled T+0.5 to T+5 hours are saved too, as the part of each that crosses the path.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
from contourpy import contour_generator
from matplotlib.colors import rgb_to_hsv
from PIL import Image
from scipy.ndimage import (
    binary_closing,
    binary_dilation,
    binary_fill_holes,
    gaussian_filter,
    label,
)

HERE = Path(__file__).resolve().parent
BRIEF = HERE.parent / "postmortem" / "monitor-placement-brief"
sys.path.insert(0, str(BRIEF))

import brief_lib  # noqa: E402

AIR_MAP = HERE / "army_mitigated026_air_a-o_250700NOV26.jpg"
STAMP = "a/o 250700NOV26"
# What the map page shows with the outlines: the box's name and the legend's note.
NAME = "Army\u2019s final maps"
NOTE = (
    "Traced and placed by this site from the U.S. Army\u2019s final forecast maps (26% of the "
    "lead airborne), to about 0.6 mile. The Army\u2019s plant marker hides the first miles."
)
MIN_PIECE_PX = 15
MIN_LINE_POINTS = 4
HIDDEN_PX = 2  # how far around the plant marker an edge counts as hidden
# The lines labeled T+0.5 to T+5 hours on the air map: two points on each, in pixels, read
# from an enlarged, gridded crop of the picture.
TIME_LINES = {
    "0.5": ((740.5, 70.5), (779.0, 94.0)),
    "2": ((715.0, 93.0), (749.0, 116.0)),
    "3": ((688.5, 107.0), (720.0, 127.0)),
    "5": ((640.0, 147.0), (676.0, 167.0)),
}
Mask = np.ndarray
Line = list[list[float]]


def air_zone() -> dict[str, Mask]:
    """Return pixel masks of the air map's shaded path (cyan) and its plant marker."""
    rgb = np.asarray(Image.open(AIR_MAP).convert("RGB")).astype(float) / 255
    hsv = rgb_to_hsv(rgb)
    hue, sat, val = hsv[..., 0] * 360, hsv[..., 1], hsv[..., 2]
    keep = np.zeros(hue.shape, dtype=bool)
    keep[brief_lib.MAP_WINDOW] = True
    cyan = (hue >= 165) & (hue <= 195) & (sat >= 0.2) & (val > 0.6) & keep
    magenta = (hue > brief_lib.MARKER_HUE[0]) & (hue < brief_lib.MARKER_HUE[1])
    marker = binary_fill_holes(binary_dilation(magenta & (sat > brief_lib.MARKER_SAT) & keep))
    return {"air": cyan, "marker": marker}


def solid(mask: Mask, bridge: int) -> Mask:
    """Close the gaps county names and lines leave in a zone, and keep its largest piece."""
    grown = np.pad(mask, bridge)
    closed = binary_closing(grown, iterations=bridge)[bridge:-bridge, bridge:-bridge]
    lab, n = label(binary_fill_holes(closed))
    sizes = [(int((lab == k).sum()), k) for k in range(1, n + 1)]
    size, best = max(sizes)
    if size < MIN_PIECE_PX:
        raise SystemExit("no shaded zone found")
    return np.asarray(lab == best)


def to_ground(ref: dict[str, float], x: np.ndarray, y: np.ndarray) -> Line:
    """Return [latitude, longitude] for pixel positions, undoing ``brief_lib.to_pixel``."""
    lon = ref["ref_lon"] + (x - ref["x0"]) / ref["k"]
    merc = brief_lib.mercator(ref["ref_lat"]) - (y - ref["y0"]) / ref["k"]
    lat = np.degrees(np.arctan(np.sinh(np.radians(merc))))
    return [[round(float(a), 4), round(float(b), 4)] for a, b in zip(lat, lon, strict=True)]


def edges(zone: Mask, marker: Mask, ref: dict[str, float]) -> list[Line]:
    """Return a zone's edge as lines on the ground, without the parts the marker hides."""
    field = gaussian_filter(zone.astype(float), 0.7)
    hidden = binary_dilation(marker, iterations=HIDDEN_PX)
    out = []
    for line in contour_generator(z=field).lines(0.5):
        xi = np.clip(np.rint(line[:, 0]).astype(int), 0, zone.shape[1] - 1)
        yi = np.clip(np.rint(line[:, 1]).astype(int), 0, zone.shape[0] - 1)
        shown = ~hidden[yi, xi]
        if shown.all():
            runs = [line]
        else:  # start at a hidden point so a closed edge isn't cut in two at its seam
            start = int(np.argmin(shown))
            order = np.roll(np.arange(len(line)), -start)
            runs, run = [], []
            for i in order:
                if shown[i]:
                    run.append(line[i])
                elif run:
                    runs.append(np.array(run))
                    run = []
            if run:
                runs.append(np.array(run))
        out += [to_ground(ref, r[:, 0], r[:, 1]) for r in runs if len(r) >= MIN_LINE_POINTS]
    return out


def time_marks(zone: Mask, ref: dict[str, float]) -> list[dict[str, Any]]:
    """Return the part of each labeled time line that crosses the shaded path."""
    out = []
    for hours, (p, q) in TIME_LINES.items():
        t = np.linspace(0, 1, 400)
        x, y = p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t
        inside = zone[np.rint(y).astype(int), np.rint(x).astype(int)]
        if not inside.any():
            continue
        i = np.nonzero(inside)[0]
        ends = np.array([i[0], i[-1]])
        out.append({"label": f"T+{hours} h", "line": to_ground(ref, x[ends], y[ends])})
    return out


def main(args: list[str]) -> None:
    """Trace both maps and write ``outlines.json``."""
    georef = HERE / "georef.json"
    if "--place" in args:
        import place_army_map  # noqa: PLC0415

        fitted = place_army_map.fit(AIR_MAP, place_army_map.boundaries())
        georef.write_text(json.dumps({"air": fitted}, indent=1) + "\n")
    air_ref = json.loads(georef.read_text())["air"]
    ground_ref = brief_lib.army_placement()
    air = air_zone()
    path = solid(air["air"], 4)
    ground = brief_lib.army_zones()
    px_mi = brief_lib.KM_PER_MI / (
        brief_lib.KM_PER_DEG * math.cos(math.radians(air_ref["ref_lat"])) / air_ref["k"]
    )
    dep5 = edges(solid(ground["dep5"], 4), ground["marker"], ground_ref)
    dep100 = edges(solid(ground["dep100"], 1), ground["marker"], ground_ref)
    out: dict[str, Any] = {
        "name": NAME,
        "note": NOTE,
        "stamp": STAMP,
        "pixelsPerMile": round(px_mi, 2),
        # "air" goes with the map's air views, "dep" with its deposition view
        "air": {
            "zones": [
                {
                    "label": "0.18 \u00b5g/m\u00b3 or more in air",
                    "lines": edges(path, air["marker"], air_ref),
                }
            ],
            "marks": time_marks(path, air_ref),
        },
        "dep": {
            "zones": [
                {"label": "5 \u00b5g/ft\u00b2 or more on the ground", "lines": dep5},
                {"label": "100 \u00b5g/ft\u00b2 or more on the ground", "lines": dep100},
            ],
        },
    }
    (HERE / "outlines.json").write_text(json.dumps(out, separators=(",", ":")) + "\n")
    for kind in ("air", "dep"):
        for z in out[kind]["zones"]:
            n = sum(len(line) for line in z["lines"])
            print(f"{kind} {z['label']}: {len(z['lines'])} line(s), {n} points")
    print("time marks:", [m["label"] for m in out["air"]["marks"]])


if __name__ == "__main__":
    main(sys.argv[1:])
