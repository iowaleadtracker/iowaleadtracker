"""Place the Army's final ground map on the ground by its county lines.

Usage (needs the network for the county boundaries)::

    python place_army_map.py

The Army's map is a small picture, about 0.6 mile per pixel, with the plume drawn over a
base map that shows county lines. The plume's upwind end is hidden under the plant marker,
so the plume itself can't say where the source is. This script finds where the picture
sits instead: it picks out the county lines in the picture and fits a Mercator scale and
an offset so that public county boundaries (Esri's generalized layer of the Census
Bureau's counties) fall on them. The fit is good to about a pixel.

Writes ``data/army_georef.json``: ``k`` (pixels per degree of longitude), the pixel
``x0``, ``y0`` of the reference point ``ref_lon``, ``ref_lat``, and the share of boundary
points that land within 1.5 px of a line in the picture.
"""

from __future__ import annotations

import itertools
import json
import urllib.parse
import urllib.request
from typing import TYPE_CHECKING

import brief_lib
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt, median_filter
from scipy.optimize import minimize

if TYPE_CHECKING:
    from pathlib import Path

COUNTIES = (
    "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/"
    "USA_Counties_Generalized_Boundaries/FeatureServer/0/query?"
)
QUERY = {
    "where": "1=1",
    "geometry": "-98.5,36.0,-86.0,42.2",
    "geometryType": "esriGeometryEnvelope",
    "inSR": "4326",
    "spatialRel": "esriSpatialRelIntersects",
    "outFields": "NAME",
    "outSR": "4326",
    "f": "geojson",
}
REF_LON, REF_LAT = -91.27, 40.81
WINDOW = (slice(5, 555), slice(235, 945))  # the map, inside its frame
STEP_DEG = 0.006  # spacing of points along the boundaries
NEAR_PX = 1.5


def boundaries() -> np.ndarray:
    """Fetch the county boundaries and return points along them (lon, lat)."""
    url = COUNTIES + urllib.parse.urlencode(QUERY)
    with urllib.request.urlopen(url, timeout=120) as resp:  # noqa: S310
        features = json.load(resp)["features"]
    pts = []
    for f in features:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for ring in (r for poly in polys for r in poly):
            r = np.array(ring)
            for a, b in itertools.pairwise(r):
                n = max(1, int(np.hypot(*(b - a)) / STEP_DEG))
                pts.append(a + (b - a) * np.linspace(0, 1, n, endpoint=False)[:, None])
    return np.unique(np.round(np.vstack(pts), 4), axis=0)


def line_distance(path: Path) -> np.ndarray:
    """Return each pixel's distance to the nearest thin dark line (capped at 4 px)."""
    gray = (np.asarray(Image.open(path).convert("RGB")).astype(float) / 255).mean(2)
    darker = median_filter(gray, size=9) - gray
    keep = np.zeros(gray.shape, dtype=bool)
    keep[WINDOW] = True
    line = (darker > 0.04) & (darker < 0.30) & (gray > 0.45) & keep
    return np.asarray(np.minimum(distance_transform_edt(~line), 4.0))


def fit(path: Path, pts: np.ndarray) -> dict[str, float]:
    """Fit the scale and offset that put the boundaries on the picture's lines."""
    dist = line_distance(path)
    dx, dy = pts[:, 0] - REF_LON, -(brief_lib.mercator(pts[:, 1]) - brief_lib.mercator(REF_LAT))

    def near(p: np.ndarray) -> np.ndarray:
        xi = np.rint(p[1] + p[0] * dx).astype(int)
        yi = np.rint(p[2] + p[0] * dy).astype(int)
        ok = (
            (xi >= WINDOW[1].start)
            & (xi < WINDOW[1].stop)
            & (yi >= WINDOW[0].start)
            & (yi < WINDOW[0].stop)
        )
        return np.asarray(dist[yi[ok], xi[ok]])

    def cost(p: np.ndarray) -> float:
        return float(near(p).mean())

    grid = [
        np.array([k, x, y])
        for k in np.arange(80, 98, 1.0)
        for x in np.arange(735, 790, 2.0)
        for y in np.arange(40, 100, 2.0)
    ]
    start = min(grid, key=cost)
    best = minimize(cost, start, method="Nelder-Mead", options={"xatol": 0.01, "fatol": 1e-5}).x
    return {
        "k": float(best[0]),
        "x0": float(best[1]),
        "y0": float(best[2]),
        "ref_lon": REF_LON,
        "ref_lat": REF_LAT,
        "share_near": float((near(best) < NEAR_PX).mean()),
    }


def main() -> None:
    """Fit the map and save the result."""
    out = {"ground": fit(brief_lib.ARMY_GROUND_MAP, boundaries())}
    (brief_lib.DATA / "army_georef.json").write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
