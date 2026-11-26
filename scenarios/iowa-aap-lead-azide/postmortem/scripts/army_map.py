"""Measure the Army's "Mitigated 0.26" map images and compare them with the tracker.

Usage (from the repository root)::

    python army_map.py ARMY_DIR FORECAST_MAP ANALYSIS_MAP > army_map.json

ARMY_DIR holds the 1200 x 675 JPEG images of the Army's advisory maps. Two issues are
measured: ``final``, stamped a/o 250700NOV26 (7 a.m. on the day of the detonation), and
``nov24``, stamped a/o 240630NOV26. Distances use each map's scale bar. Positions are
measured from an anchor, the pixel taken to be the detonation point:

- ``tip``: the upwind tip of the ground plume itself, where the 100 µg/ft² wedge starts
  at the magenta plant marker (read from an enlarged crop, good to about 2 px);
- ``box``: the center of the magenta marker, 2 to 3 miles from the tip.

North is assumed up. Shaded areas can't be measured reliably at 1.7 to 2.5 px per mile
with anti-aliased edges, so areas quoted in the text are the ones printed on the maps.

The final air map draws the cloud's whole path and marks it with lines labeled T+0.5,
T+2, T+3 and T+5 hours. Each line's end points were read from an enlarged, gridded crop;
the script intersects them with the path's long axis. The Nov. 24 air map shows three
separate shapes instead.
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
from scipy.ndimage import binary_closing, binary_fill_holes, label

MAP_WINDOW = (slice(0, 560), slice(230, 950))  # the map itself, without legend and text
CELL = 0.005  # deg, grid for the traced shapes
MIN_BLOB_PX = 15
Point = tuple[float, float]
# px_per_mi: from the scale bar's tick marks. tip, box: anchors on the ground map.
# air_shift: the air image's offset from the ground image (their plant markers differ).
MAPS: dict[str, dict[str, Any]] = {
    "final": {
        "stamp": "250700NOV26",
        "px_per_mi": (1086 - 258) / 500,
        "tip": (761.5, 69.5),
        "box": (766.5, 68.0),
        "air_shift": (-0.5, 4.0),
        # Time markers on the air map: two points on each line (pixels).
        "cuts": {
            "0.5": ((740.5, 70.5), (779.0, 94.0)),
            "2": ((715.0, 93.0), (749.0, 116.0)),
            "3": ((688.5, 107.0), (720.0, 127.0)),
            "5": ((640.0, 147.0), (676.0, 167.0)),
        },
    },
    "nov24": {
        "stamp": "240630NOV26",
        "px_per_mi": (879 - 250) / 250,
        "tip": (770.0, 68.5),
        "box": (775.5, 71.0),
        "air_shift": (0.0, 0.0),
        "cuts": {},
    },
}


def image(army_dir: Path, kind: str, name: str) -> Path:
    """Return the path of one map image (kind is ``ground`` or ``air``)."""
    return army_dir / f"army_mitigated026_{kind}_a-o_{MAPS[name]['stamp']}.jpg"


def nearest_piece(mask: np.ndarray, tip: Point) -> np.ndarray:
    """Return the connected piece of a mask that starts nearest the plume tip.

    Drops other map features of the same color (rivers and lakes are blue).
    """
    lab, n = label(mask, structure=np.ones((3, 3)))
    best, best_d = mask, math.inf
    for k in range(1, n + 1):
        ys, xs = np.nonzero(lab == k)
        if len(xs) < MIN_BLOB_PX:
            continue
        d = float(np.hypot(xs - tip[0], ys - tip[1]).min())
        if d < best_d:
            best, best_d = lab == k, d
    return best


def masks(path: Path, tip: Point) -> dict[str, np.ndarray]:
    """Return boolean pixel masks of the map's shadings, by hue and saturation.

    Along the plume the 100 µg/ft² wedge is blue (hue 195-270), turning purple (270-298)
    where it lies over the magenta marker; the 5 µg/ft² zone is green (92-135). The 5 zone
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
    cyan = (hue >= 165) & (hue <= 195) & (sat >= 0.2) & (hsv[..., 2] > 0.6)
    wedge = nearest_piece(binary_closing((blue | purple) & keep, iterations=1), tip)
    dep5 = nearest_piece(binary_closing((green & keep) | wedge, iterations=1), tip)
    return {"dep5": dep5, "dep100": wedge, "air": cyan & keep}


def measure(mask: np.ndarray, anchor: Point, px_per_mi: float) -> dict[str, float]:
    """Return a shape's nearest, farthest and center distance (mi) and bearings."""
    ys, xs = np.nonzero(mask)
    dx, dy = xs - anchor[0], ys - anchor[1]
    d = np.hypot(dx, dy) / px_per_mi
    b = (np.degrees(np.arctan2(dx, -dy)) + 360) % 360
    i = int(np.argmax(d))
    cx, cy = dx.mean(), dy.mean()
    return {
        "near_mi": float(d.min()),
        "far_mi": float(d[i]),
        "far_bearing": float(b[i]),
        "center_mi": float(math.hypot(cx, cy) / px_per_mi),
        "center_bearing": float((math.degrees(math.atan2(cx, -cy)) + 360) % 360),
        "drawn_area_mi2": float(mask.sum() / px_per_mi**2),
    }


def axis(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Return a shape's centroid, the unit vector of its long axis (pointing the way the
    plume travels, in pixels) and that direction's bearing.
    """  # noqa: D205
    ys, xs = np.nonzero(mask)
    pts = np.c_[xs, ys].astype(float)
    c = pts.mean(0)
    _, _, vt = np.linalg.svd(pts - c)
    v = vt[0] if vt[0][0] < 0 else -vt[0]  # west
    return c, v, float((math.degrees(math.atan2(v[0], -v[1])) + 360) % 360)


def to_fields(mask: np.ndarray, anchor: Point, px_per_mi: float) -> lib.Fields:
    """Put a traced shape on a lon-lat grid (1 inside), placed from the anchor."""
    ys, xs = np.nonzero(mask)
    la, lo = to_latlon(xs, ys, anchor, px_per_mi)
    lat = np.arange(38.9, 41.4, CELL)
    lon = np.arange(-94.2, -90.4, CELL)
    r = np.zeros((len(lat), len(lon)), dtype=bool)
    r[
        np.clip(np.rint((la - lat[0]) / CELL).astype(int), 0, len(lat) - 1),
        np.clip(np.rint((lo - lon[0]) / CELL).astype(int), 0, len(lon) - 1),
    ] = True
    close = max(2, round(1.5 * lib.KM_PER_MI / px_per_mi / (CELL * lib.KM_PER_DEG) / 2) + 2)
    grid = binary_fill_holes(binary_closing(r, iterations=close)).astype(float)
    cell = (CELL * lib.KM_PER_DEG / lib.KM_PER_MI) ** 2 * np.cos(np.radians(lat))
    return lib.Fields(
        lat=lat, lon=lon, air={}, dep={0: grid}, snap={}, cell_mi2=cell, released_kg=0.0
    )


def to_latlon(xs: Any, ys: Any, anchor: Point, px_per_mi: float) -> tuple[Any, Any]:  # noqa: ANN401
    """Convert pixels to latitude and longitude, with the anchor at the plant."""
    la = lib.LAT0 - (np.asarray(ys) - anchor[1]) / px_per_mi * lib.KM_PER_MI / lib.KM_PER_DEG
    k = lib.KM_PER_DEG * math.cos(math.radians(lib.LAT0))
    lo = lib.LON0 + (np.asarray(xs) - anchor[0]) / px_per_mi * lib.KM_PER_MI / k
    return la, lo


def air_anchor(name: str, air_mask: np.ndarray) -> Point:
    """Return the air map's anchor: the point on the cloud path's axis nearest the tip."""
    m = MAPS[name]
    tip = np.array(m["tip"]) + np.array(m["air_shift"])
    if not m["cuts"]:
        return (float(tip[0]), float(tip[1]))
    c, v, _ = axis(air_mask)
    p = c + ((tip - c) @ v) * v
    return (float(p[0]), float(p[1]))


def cuts(name: str, air_mask: np.ndarray) -> dict[str, dict[str, float]]:
    """Return where each labeled time line crosses the cloud path's axis (final map)."""
    m = MAPS[name]
    c, v, bearing = axis(air_mask)
    origin = np.array(air_anchor(name, air_mask))
    out = {}
    for hours, (q1, q2) in m["cuts"].items():
        e = np.array(q2) - np.array(q1)
        t = np.linalg.solve(np.array([v, -e]).T, np.array(q1) - c)[0]
        p = c + t * v
        la, lo = to_latlon(p[0], p[1], (origin[0], origin[1]), m["px_per_mi"])
        out[hours] = {
            "miles": float(np.hypot(*(p - origin)) / m["px_per_mi"]),
            "bearing": bearing,
            "lat": float(la),
            "lon": float(lo),
        }
    return out


def air_blobs(mask: np.ndarray, tip: Point, px_per_mi: float) -> list[np.ndarray]:
    """Split the air shading into its separate pieces, nearest the source first."""
    lab, n = label(mask, structure=np.ones((3, 3)))
    blobs = [lab == k for k in range(1, n + 1) if (lab == k).sum() >= MIN_BLOB_PX]
    return sorted(blobs, key=lambda b: measure(b, tip, px_per_mi)["center_mi"])


def main(args: list[str]) -> None:
    """Measure both issues of the map under each anchor and print JSON."""
    army_dir = Path(args[0])
    models = {
        "tracker forecast": lib.tracker(Path(args[1]), moved=False),
        "tracker analysis": lib.tracker(Path(args[2]), moved=False),
    }
    out: dict[str, Any] = {}
    for name, m in MAPS.items():
        px = m["px_per_mi"]
        ground = masks(image(army_dir, "ground", name), m["tip"])
        air = masks(image(army_dir, "air", name), m["tip"])["air"]
        if m["cuts"]:  # the cloud path is the piece nearest the plant
            air = nearest_piece(air, m["tip"])
        res: dict[str, Any] = {
            "stamp": m["stamp"],
            "px_per_mi": px,
            "ground_axis_bearing": axis(ground["dep5"])[2],
            "anchors": {},
        }
        for aname in ("tip", "box"):
            anchor = m[aname]
            a: dict[str, Any] = {
                "ground_5": measure(ground["dep5"], anchor, px),
                "ground_100": measure(ground["dep100"], anchor, px),
                "overlap_ground_5": {},
            }
            army5 = to_fields(ground["dep5"], anchor, px)
            for mname, f in models.items():
                ov = lib.overlap(army5, army5.dep[0], f, f.dep[8], 5 * lib.UG_FT2)
                a["overlap_ground_5"][mname] = ov
            res["anchors"][aname] = a
        if m["cuts"]:
            origin = air_anchor(name, air)
            res["air_path"] = measure(air, origin, px) | {"axis_bearing": axis(air)[2]}
            res["air_cuts"] = cuts(name, air)
        else:
            tip = (m["tip"][0] + m["air_shift"][0], m["tip"][1] + m["air_shift"][1])
            res["air_pieces"] = [measure(b, tip, px) for b in air_blobs(air, tip, px)]
        out[name] = res
    json.dump(out, sys.stdout, indent=1)
    sys.stdout.write("\n")


if __name__ == "__main__":
    with lib.nominal_origin():  # a comparison of shapes, placed at the Army plume's own tip
        main(sys.argv[1:])
