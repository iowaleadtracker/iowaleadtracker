"""Figure 7: the modeled cloud and EPA's sites over aerial imagery.

Usage (from the repository root, ``HYSPLIT_DIR`` set; needs the network for the imagery)::

    python aerial_map.py FORECAST_MAPS ANALYSIS_MAPS HYSPLIT_RUN ARMY_DIR EPA_DIR OUT.png

Outlines where the highest hourly mean air at the ground is 0.18 µg/m³ or more for the
lowest case (7% of the lead airborne), from the modeled source, for the tracker's forecast,
the tracker on analyzed weather and HYSPLIT on NOAA ARL's archived weather. The two runs
on analyzed weather are dashed. The zones traced from the Army's final ground map (lead
on the ground of 5 and 100 µg/ft² or more, its 26% case) are shaded. They are placed by
the county lines on the Army's map (``georeference.py``, saved in
``data/army_georef.json``), which is good to about a pixel, 0.6 mile. The zones' first
miles are hidden under the plant marker on the Army's map and are not drawn. The imagery
is Esri World Imagery, fetched as map tiles when the figure is drawn.
"""

from __future__ import annotations

import csv
import io
import json
import math
import sys
import urllib.request
from pathlib import Path

import army_map
import figure
import georeference
import lib
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from PIL import Image
from scipy.ndimage import binary_closing, binary_fill_holes, gaussian_filter, map_coordinates

LOW = 0.07
TILES = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
)
BOX = (-91.62, -91.19, 40.60, 40.865)  # west, east, south, north
ZOOM = 13
XACT = ("AS01", "AS02", "AS03", "AS04")
NAMED = ("AS06", "AS12", "AS13")
HALO = [pe.Stroke(linewidth=4.2, foreground="white"), pe.Normal()]
BOXED = {"fc": "white", "ec": "none", "alpha": 0.9, "pad": 2}
# The forecast is solid; the runs on weather analyzed afterward are dashed.
STYLE = {"forecast": "solid", "analysis": (0, (5, 2.5)), "hysplit": (0, (5, 2.5))}
ARMY_LABEL = "Army map (final): lead on the ground, 5 and 100 µg/ft² or more, 26% case"


def army_zones(army_dir: Path) -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray]]:
    """Trace the ground zones on the Army's final map; return them on a lon-lat grid."""
    name = figure.ARMY_MAP
    traced = army_map.masks(army_map.image(army_dir, "ground", name), army_map.MAPS[name]["tip"])
    ref = json.loads((Path(__file__).resolve().parents[1] / "data/army_georef.json").read_text())
    west, east, south, north = BOX
    lon, lat = np.arange(west, east, 0.002), np.arange(south, north, 0.002)
    x, y = georeference.to_pixel(ref["ground"], *np.meshgrid(lon, lat))
    zones = {}
    for key, bridge in (("dep5", 4), ("dep100", 1)):  # county names are printed over the zones
        grown = np.pad(traced[key], bridge)
        closed = binary_closing(grown, iterations=bridge)[bridge:-bridge, bridge:-bridge]
        solid = binary_fill_holes(closed).astype(float)
        zones[key] = map_coordinates(gaussian_filter(solid, 0.7), [y, x], order=1)
    return lon, lat, zones


def basemap() -> tuple[Image.Image, tuple[float, float, float, float]]:
    """Fetch and stitch the imagery tiles covering BOX; return the image and its extent."""
    west, east, south, north = BOX
    n = 2**ZOOM

    def col(lon: float) -> int:
        return int((lon + 180) / 360 * n)

    def row(lat: float) -> int:
        return int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)

    def lat_of(r: int) -> float:
        return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * r / n))))

    x0, x1, y0, y1 = col(west), col(east), row(north), row(south)
    img = Image.new("RGB", (256 * (x1 - x0 + 1), 256 * (y1 - y0 + 1)))
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            url = TILES.format(z=ZOOM, x=x, y=y)
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})  # noqa: S310
            with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
                img.paste(Image.open(io.BytesIO(resp.read())), (256 * (x - x0), 256 * (y - y0)))
    return img, (x0 / n * 360 - 180, (x1 + 1) / n * 360 - 180, lat_of(y1 + 1), lat_of(y0))


def worst(f: lib.Fields) -> np.ndarray:
    """Return the highest hourly mean air in each cell."""
    return np.max(np.stack([f.air[h] for h in sorted(f.air)]), axis=0)


def main(args: list[str]) -> None:
    """Draw the figure."""
    fc_dir, an_dir, hy_run, army_dir, epa, out = (Path(a) for a in args)
    runs = {
        "forecast": lib.tracker(fc_dir / "permit-0900.html"),
        "analysis": lib.tracker(an_dir / "an_permit.html"),
        "hysplit": lib.hysplit(hy_run),
    }
    with (epa / "epa_air_stations.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    west, east, south, north = BOX
    img, extent = basemap()
    fig, ax = plt.subplots(figsize=(11, 8.6), constrained_layout=True)
    ax.imshow(img, extent=extent, interpolation="bilinear")
    ax.set_xlim(west, east)
    ax.set_ylim(south, north)
    ax.set_aspect(1 / math.cos(math.radians(lib.LAT0)))
    plon, plat, zones = army_zones(army_dir)
    green = figure.C["army"]
    ax.contourf(plon, plat, zones["dep5"], [0.5, np.inf], colors=[green], alpha=0.25)
    ax.contourf(plon, plat, zones["dep100"], [0.5, np.inf], colors=[green], alpha=0.35)
    for key in ("dep5", "dep100"):
        edge = ax.contour(plon, plat, zones[key], [0.5], colors=[green])
        edge.set(linewidths=2, path_effects=HALO)
    for key, f in runs.items():
        field = gaussian_filter(worst(f), 1.5) if key == "hysplit" else worst(f)
        cs = ax.contour(f.lon, f.lat, field * LOW, levels=[lib.ARMY_AIR], colors=[figure.C[key]])
        cs.set(linewidths=2.4, linestyles=[STYLE[key]], path_effects=HALO)
    for r in rows:
        name, la, lo = r["station_id"].replace("-", ""), float(r["lat"]), float(r["lon"])
        if not (west < lo < east and south < la < north):
            continue
        if name in XACT:
            d, b = lib.dist_brg(la, lo)
            ax.plot(lo, la, "D", ms=10, mfc="white", mec=figure.INK, mew=2, zorder=8)
            ax.annotate(
                f"{name}  {float(d):.1f} mi at {float(b):.0f}°",
                (lo, la),
                xytext=(11, 9),
                textcoords="offset points",
                fontsize=9,
                weight="bold",
                color=figure.INK,
                bbox=BOXED,
                zorder=9,
            )
            continue
        ax.plot(lo, la, "s", ms=6, mfc="white", mec=figure.INK, mew=1.2, zorder=7)
        if name in NAMED:
            ax.annotate(
                name,
                (lo, la),
                xytext=(8, -12),
                textcoords="offset points",
                fontsize=8,
                color=figure.INK,
                bbox=BOXED,
                zorder=9,
            )
    ax.plot(lib.LON0, lib.LAT0, "*", ms=22, mfc="#ffd400", mec=figure.INK, mew=1.5, zorder=10)
    ax.annotate(
        "Modeled source\n(the two magazines)",
        (lib.LON0, lib.LAT0),
        xytext=(12, 10),
        textcoords="offset points",
        fontsize=9,
        weight="bold",
        color=figure.INK,
        bbox=BOXED,
        zorder=10,
    )
    five = 5 * lib.KM_PER_MI / (lib.KM_PER_DEG * math.cos(math.radians(lib.LAT0)))
    x0, y0 = west + 0.015, south + 0.012
    ax.plot([x0, x0 + five], [y0, y0], color="white", lw=5, solid_capstyle="butt", zorder=9)
    ax.plot([x0, x0 + five], [y0, y0], color=figure.INK, lw=2.5, solid_capstyle="butt", zorder=10)
    ax.annotate(
        "5 miles",
        (x0, y0),
        xytext=(0, 7),
        textcoords="offset points",
        fontsize=9,
        color="white",
        weight="bold",
        path_effects=[pe.Stroke(linewidth=2.5, foreground=figure.INK), pe.Normal()],
    )
    ax.set_xticks([])
    ax.set_yticks([])
    square = {"marker": "s", "ls": "", "mfc": "white", "mec": figure.INK}
    handles = [
        *[
            Line2D([], [], color=figure.C[k], lw=2.4, ls=STYLE[k], label=figure.NAMES[k])
            for k in runs
        ],
        Patch(fc=green, ec=green, alpha=0.5, label=ARMY_LABEL),
        Line2D(
            [],
            [],
            marker="D",
            ls="",
            mfc="white",
            mec=figure.INK,
            mew=2,
            ms=9,
            label="EPA real-time lead monitor",
        ),
        Line2D([], [], **square, mew=1.2, ms=6, label="EPA sampling site, no results posted"),
        Line2D(
            [], [], marker="*", ls="", mfc="#ffd400", mec=figure.INK, ms=16, label="Modeled source"
        ),
    ]
    legend = ax.legend(handles=handles, fontsize=8.5, loc="lower right", framealpha=0.97)
    legend.set_zorder(30)
    figure.title(
        fig,
        "Modeled highest hourly mean lead in air of 0.18 µg/m³ or more, lowest case (7%), "
        "and the ground zones on the Army's map.\nModel estimates, not measurements.",
    )
    fig.get_layout_engine().set(rect=(0, 0.075, 1, 0.9))
    fig.text(
        0.99,
        0.045,
        "Imagery: Esri World Imagery (Esri, Maxar, Earthstar Geographics)",
        fontsize=7.5,
        color=figure.MUTED,
        ha="right",
        va="bottom",
    )
    fig.savefig(out, dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main(sys.argv[1:])
