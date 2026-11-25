"""Measure the Army's "Mitigated 0.26" map images and compare them with the tracker.

Usage (from the repository root)::

    python army_map.py GROUND.jpg AIR.jpg FORECAST_MAP ANALYSIS_MAP > army.json

The images are 1200 x 675 JPEGs of the Army's advisory. Distances use the map's scale
bar. Positions are measured from an anchor, the pixel taken to be the detonation point:

- ``tip``: the upwind tip of the plume itself, where the 100 µg/ft² wedge starts inside
  the magenta source box (read from an enlarged crop, good to about 2 px);
- ``box``: the center of the magenta box, about 2.6 miles east-southeast of the tip.

North is assumed up; a fit through ten labeled cities gives the map's rotation and an
independent, rougher position for the plant. Shaded areas can't be measured reliably
at 2.5 px per mile with anti-aliased edges, so areas quoted in the text are the ones
the Army printed on the map.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import lib
import numpy as np
from matplotlib.colors import rgb_to_hsv
from PIL import Image
from scipy.ndimage import binary_closing, label

PX_PER_MI = (879 - 250) / 250  # scale bar: "0" at x=250, "250" at x=879
ANCHORS = {"tip": (770.0, 68.5), "box": (775.5, 71.0)}
MAP_WINDOW = (slice(0, 560), slice(230, 950))  # the map itself, without text panels
CELL = 0.005  # deg, grid for the traced shapes
MIN_BLOB_PX = 15
# Labeled cities: pixel of the marker (found on the air map) and coordinates.
CITIES = {
    "Kansas City": (331, 352, 39.0997, -94.5786),
    "St. Louis": (925, 439, 38.6270, -90.1994),
    "Peoria": (1001, 73, 40.6936, -89.5890),
    "Springfield": (993, 234, 39.7817, -89.6501),
    "Columbia": (642, 380, 38.9517, -92.3341),
    "Jefferson City": (656, 455, 38.5767, -92.1735),
    "Quincy": (753, 201, 39.9356, -91.4099),
    "St. Joseph": (288, 244, 39.7675, -94.8467),
    "Decatur": (1070, 223, 39.8403, -88.9548),
    "Lawrence": (240, 383, 38.9717, -95.2353),
}


def masks(path: Path) -> dict[str, np.ndarray]:
    """Return boolean pixel masks of the map's shadings, by hue and saturation.

    Along the plume the 100 µg/ft² wedge is blue (hue 195-270), turning purple (270-298)
    where it lies over the magenta box; the 5 µg/ft² zone is green (92-135). The 5 zone
    contains the 100 zone. The air shading is cyan.
    """
    rgb = np.asarray(Image.open(path).convert("RGB")).astype(float) / 255
    hsv = rgb_to_hsv(rgb)
    hue, sat = hsv[..., 0] * 360, hsv[..., 1]
    keep = np.zeros(hue.shape, dtype=bool)
    keep[MAP_WINDOW] = True
    green = (hue >= 92) & (hue <= 135) & (sat >= 0.26)
    blue = (hue >= 195) & (hue <= 270) & (sat >= 0.25)
    purple = (hue > 270) & (hue <= 298) & (sat >= 0.35)
    cyan = (hue >= 170) & (hue <= 190) & (sat >= 0.35) & (hsv[..., 2] > 0.7)
    wedge = largest(binary_closing((blue | purple) & keep, iterations=1))
    return {
        "dep5": largest(binary_closing((green & keep) | wedge, iterations=1)),
        "dep100": wedge,
        "air": cyan & keep,
    }


def largest(mask: np.ndarray) -> np.ndarray:
    """Return the connected piece of a mask that starts nearest the plume tip.

    Drops other map features of the same color (rivers and lakes are blue).
    """
    lab, n = label(mask, structure=np.ones((3, 3)))
    tx, ty = ANCHORS["tip"]
    best, best_d = mask, math.inf
    for k in range(1, n + 1):
        ys, xs = np.nonzero(lab == k)
        if len(xs) < MIN_BLOB_PX:
            continue
        d = float(np.hypot(xs - tx, ys - ty).min())
        if d < best_d:
            best, best_d = lab == k, d
    return best


def measure(mask: np.ndarray, anchor: tuple[float, float]) -> dict[str, float]:
    """Return a shape's nearest, farthest and center distance (mi) and bearings."""
    ys, xs = np.nonzero(mask)
    dx, dy = xs - anchor[0], ys - anchor[1]
    d = np.hypot(dx, dy) / PX_PER_MI
    b = (np.degrees(np.arctan2(dx, -dy)) + 360) % 360
    i = int(np.argmax(d))
    cx, cy = dx.mean(), dy.mean()
    return {
        "near_mi": float(d.min()),
        "far_mi": float(d[i]),
        "far_bearing": float(b[i]),
        "center_mi": float(math.hypot(cx, cy) / PX_PER_MI),
        "center_bearing": float((math.degrees(math.atan2(cx, -cy)) + 360) % 360),
        "drawn_area_mi2": float(mask.sum() / PX_PER_MI**2),
    }


def axis_bearing(mask: np.ndarray) -> float:
    """Return the travel bearing of a plume's long axis (independent of the anchor)."""
    ys, xs = np.nonzero(mask)
    pts = np.c_[xs, -ys].astype(float)
    _, _, vt = np.linalg.svd(pts - pts.mean(0))
    ex, ny = vt[0] if vt[0][0] < 0 else -vt[0]  # point west, the way the plume travels
    return float((math.degrees(math.atan2(ex, ny)) + 360) % 360)


def city_fit() -> dict[str, float]:
    """Fit pixel = affine(lat, lon) through the cities; report rotation and the plant."""
    p = np.array([[la, lo, 1.0] for _, _, la, lo in CITIES.values()])
    x = np.array([c[0] for c in CITIES.values()], dtype=float)
    y = np.array([c[1] for c in CITIES.values()], dtype=float)
    cx, cy = np.linalg.lstsq(p, x, rcond=None)[0], np.linalg.lstsq(p, y, rcond=None)[0]
    resid = np.hypot(p @ cx - x, p @ cy - y)
    px, py = np.array([lib.LAT0, lib.LON0, 1.0]) @ cx, np.array([lib.LAT0, lib.LON0, 1.0]) @ cy
    tip = ANCHORS["tip"]
    return {
        "north_rotation_deg": float(math.degrees(math.atan2(cx[0], -cy[0]))),
        "px_per_mi_from_fit": float(-cy[0] / (lib.KM_PER_DEG / lib.KM_PER_MI)),
        "rms_residual_px": float(np.sqrt((resid**2).mean())),
        "plant_minus_tip_mi_east": float((px - tip[0]) / PX_PER_MI),
        "plant_minus_tip_mi_north": float(-(py - tip[1]) / PX_PER_MI),
    }


def to_fields(mask: np.ndarray, anchor: tuple[float, float]) -> lib.Fields:
    """Put a traced shape on a lon-lat grid (1 inside), placed from the anchor."""
    ys, xs = np.nonzero(mask)
    la = lib.LAT0 - (ys - anchor[1]) / PX_PER_MI * lib.KM_PER_MI / lib.KM_PER_DEG
    lo = lib.LON0 + (xs - anchor[0]) / PX_PER_MI * lib.KM_PER_MI / (
        lib.KM_PER_DEG * math.cos(math.radians(lib.LAT0))
    )
    lat = np.arange(38.9, 41.4, CELL)
    lon = np.arange(-94.2, -90.4, CELL)
    r = np.zeros((len(lat), len(lon)), dtype=bool)
    r[
        np.clip(np.rint((la - lat[0]) / CELL).astype(int), 0, len(lat) - 1),
        np.clip(np.rint((lo - lon[0]) / CELL).astype(int), 0, len(lon) - 1),
    ] = True
    grid = binary_closing(r, iterations=4).astype(float)
    cell = (CELL * lib.KM_PER_DEG / lib.KM_PER_MI) ** 2 * np.cos(np.radians(lat))
    return lib.Fields(
        lat=lat, lon=lon, air={}, dep={0: grid}, snap={}, cell_mi2=cell, released_kg=0.0
    )


def air_blobs(mask: np.ndarray) -> list[np.ndarray]:
    """Split the air shading into its separate pieces, nearest the source first."""
    lab, n = label(mask, structure=np.ones((3, 3)))
    blobs = [lab == k for k in range(1, n + 1) if (lab == k).sum() >= MIN_BLOB_PX]
    tip = ANCHORS["tip"]
    return sorted(blobs, key=lambda m: measure(m, tip)["center_mi"])


def main(args: list[str]) -> None:
    """Measure both maps under each anchor and print JSON."""
    ground, air = masks(Path(args[0])), masks(Path(args[1]))
    models = {
        "tracker forecast": lib.tracker(Path(args[2])),
        "tracker analysis": lib.tracker(Path(args[3])),
    }
    out: dict[str, Any] = {
        "px_per_mi": PX_PER_MI,
        "city_fit": city_fit(),
        "ground_axis_bearing": axis_bearing(ground["dep5"]),
        "anchors": {},
    }
    for name, anchor in ANCHORS.items():
        a: dict[str, Any] = {
            "ground_5": measure(ground["dep5"], anchor),
            "ground_100": measure(ground["dep100"], anchor),
            "air_pieces": [measure(m, anchor) for m in air_blobs(air["air"])],
            "overlap_ground_5": {},
        }
        army5 = to_fields(ground["dep5"], anchor)
        for mname, f in models.items():
            a["overlap_ground_5"][mname] = lib.overlap(
                army5, army5.dep[0], f, f.dep[8], 5 * lib.UG_FT2
            ) | {"army_traced_mi2": float((army5.dep[0] * army5.cell_mi2[:, None]).sum())}
        out["anchors"][name] = a
    json.dump(out, sys.stdout, indent=1)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main(sys.argv[1:])
