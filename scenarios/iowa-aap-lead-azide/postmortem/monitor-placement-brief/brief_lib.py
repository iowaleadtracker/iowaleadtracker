"""Shared pieces of the monitor-placement brief.

The modeled source, distances and bearings from it, the saved model fields, and the
Army's final ground map: how its shaded zones are picked out of the picture and where the
picture sits on the ground.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from matplotlib.colors import rgb_to_hsv
from PIL import Image
from scipy.ndimage import binary_closing, binary_dilation, binary_fill_holes, label

DATA = Path(__file__).resolve().parent / "data"
KM_PER_DEG = 111.195
KM_PER_MI = 1.609344
ARMY_AIR = 0.18e-9  # kg/m³, the line on the Army's air map
UG = 1e9  # kg/m³ to µg/m³

# The release is modeled from the sources in data/source.json: two magazines, half of the
# lead each, given as offsets from the point the site used for the whole plant. LAT0, LON0
# is their share-weighted midpoint; every distance and bearing is measured from it.
_SRC = json.loads((DATA / "source.json").read_text())
_NOMINAL_LAT, _NOMINAL_LON = _SRC["nominal_point"]["lat"], _SRC["nominal_point"]["lon"]
_KM_PER_DEG_LON = KM_PER_DEG * math.cos(math.radians(_NOMINAL_LAT))
_SOURCES = [(s["north_km"], s["east_km"], s["share"]) for s in _SRC["sources"]]
LAT0 = _NOMINAL_LAT + sum(n * w for n, _, w in _SOURCES) / KM_PER_DEG
LON0 = _NOMINAL_LON + sum(e * w for _, e, w in _SOURCES) / _KM_PER_DEG_LON

Grid = tuple[np.ndarray, np.ndarray, np.ndarray]  # lon, lat, field on (lat, lon)
RUNS = ("forecast", "analysis", "hysplit")

# The Army's final "Mitigated 0.26" ground map, a 1200 x 675 picture.
ARMY_GROUND_MAP = DATA / "army/army_mitigated026_ground_a-o_250700NOV26.jpg"
MAP_WINDOW = (slice(0, 560), slice(230, 950))  # the map itself, without legend and text
MIN_BLOB_PX = 15
PLUME_TIP = (761.5, 69.5)  # pixel where the plume comes out from under the plant marker
MARKER_HUE, MARKER_SAT = (285, 340), 0.35  # the magenta plant marker


def source_coordinates() -> list[tuple[float, float]]:
    """Return the latitude and longitude of each modeled source."""
    return [
        (_NOMINAL_LAT + n / KM_PER_DEG, _NOMINAL_LON + e / _KM_PER_DEG_LON) for n, e, _ in _SOURCES
    ]


def dist_brg(lat: float, lon: float) -> tuple[float, float]:
    """Return miles and bearing (degrees from north) from the modeled source, flat-Earth."""
    dy = (lat - LAT0) * KM_PER_DEG
    dx = (lon - LON0) * KM_PER_DEG * math.cos(math.radians(LAT0))
    return math.hypot(dx, dy) / KM_PER_MI, (math.degrees(math.atan2(dx, dy)) + 360) % 360


def load_fields() -> dict[str, Grid]:
    """Read the three modeled fields the map is drawn from (see data/README.md)."""
    z = np.load(DATA / "model_fields.npz")
    return {k: (z[f"{k}_lon"], z[f"{k}_lat"], z[f"{k}_air"].astype(float)) for k in RUNS}


def _nearest_piece(mask: np.ndarray) -> np.ndarray:
    """Return the connected piece of a mask that starts nearest the plume tip.

    Drops other map features of the same color (rivers and lakes are blue).
    """
    lab, n = label(mask, structure=np.ones((3, 3)))
    best, best_d = mask, math.inf
    for k in range(1, n + 1):
        ys, xs = np.nonzero(lab == k)
        if len(xs) < MIN_BLOB_PX:
            continue
        d = float(np.hypot(xs - PLUME_TIP[0], ys - PLUME_TIP[1]).min())
        if d < best_d:
            best, best_d = lab == k, d
    return best


def army_zones() -> dict[str, np.ndarray]:
    """Return pixel masks of the Army map's ground zones and its plant marker.

    Along the plume the 100 µg/ft² wedge is blue (hue 195-270), turning purple (270-298)
    where it lies over the magenta marker; the 5 µg/ft² zone is green (92-135) and
    contains the 100 zone. The marker hides whatever the map shows under it.
    """
    rgb = np.asarray(Image.open(ARMY_GROUND_MAP).convert("RGB")).astype(float) / 255
    hsv = rgb_to_hsv(rgb)
    hue, sat = hsv[..., 0] * 360, hsv[..., 1]
    keep = np.zeros(hue.shape, dtype=bool)
    keep[MAP_WINDOW] = True
    green = (hue >= 92) & (hue <= 135) & (sat >= 0.26)
    blue = (hue >= 195) & (hue <= 270) & (sat >= 0.25)
    purple = (hue > 270) & (hue <= 298) & (sat >= 0.35)
    wedge = _nearest_piece(binary_closing((blue | purple) & keep, iterations=1))
    dep5 = _nearest_piece(binary_closing((green & keep) | wedge, iterations=1))
    magenta = (hue > MARKER_HUE[0]) & (hue < MARKER_HUE[1]) & (sat > MARKER_SAT)
    marker = binary_fill_holes(binary_dilation(magenta))
    return {"dep5": dep5, "dep100": wedge, "marker": marker}


def mercator(lat: np.ndarray | float) -> np.ndarray:
    """Return the Mercator ordinate of a latitude, in degrees."""
    return np.asarray(np.degrees(np.arcsinh(np.tan(np.radians(lat)))))


def army_placement() -> dict[str, float]:
    """Return where the Army's map sits on the ground (written by place_army_map.py)."""
    placed: dict[str, float] = json.loads((DATA / "army_georef.json").read_text())["ground"]
    return placed


def to_pixel(ref: dict[str, float], lon: np.ndarray, lat: np.ndarray) -> tuple[np.ndarray, ...]:
    """Return the Army map's pixel coordinates (x, y) of longitudes and latitudes."""
    x = ref["x0"] + ref["k"] * (np.asarray(lon) - ref["ref_lon"])
    y = ref["y0"] - ref["k"] * (mercator(lat) - mercator(ref["ref_lat"]))
    return x, y
