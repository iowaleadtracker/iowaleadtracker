"""Postmortem figure: tracker forecast, HYSPLIT on the analysis, and the Army's map.

Draws the tracker's published 9 a.m. forecast, HYSPLIT run on the 9 a.m. HRRR analysis
held for 8 hours, and the Army's "Mitigated 0.26" map (digitized from its images).

Usage (from the repository root)::

    python figure.py CASE SCALE OUT.png TRACKER_MAP HYSPLIT_RUN ARMY_AIR.jpg ARMY_GROUND.jpg

CASE is the tracker's case id (mid or permit) and SCALE the share of HYSPLIT's 100%
release to draw (0.26 or 1.0).
"""

from __future__ import annotations

import math
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from PIL import Image
from scipy.ndimage import binary_closing, gaussian_filter

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import forecast_summary as fs

if TYPE_CHECKING:
    from matplotlib.axes import Axes

LAT0, LON0 = 40.825518, -91.266502
UG = fs.KG_M2_PER_UG_FT2
PX_PER_MI = (879 - 250) / 250  # the Army map's scale bar: 0 at x=250 px, 250 mi at x=879 px
DEG_LON_PER_MI = 1.609344 / (111.195 * math.cos(math.radians(LAT0)))
DEG_LAT_PER_MI = 1.609344 / 111.195
ARMY_DEP_SOURCE = (776, 71)  # center of the magenta source box (pixels)
ARMY_AIR_SOURCE = (775, 69)
ARMY_CELL = 0.01  # deg, grid the traced Army areas are put on
TOWNS = {
    "Middletown", "Burlington", "West Point", "Fort Madison", "Donnellson", "Keokuk", "Kahoka",
    "Canton", "Quincy", "Palmyra", "Hannibal", "Mount Pleasant", "Farmington",
}  # fmt: skip
C_TR, C_HY, C_AR = "#d95f02", "#1b6ca8", "#2a9d8f"
Mask = Callable[[np.ndarray, np.ndarray, np.ndarray], np.ndarray]


def green(r: np.ndarray, g: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Army map, 5 µg/ft² shading."""
    return np.asarray((r < 150) & (g > 140) & (b < 120) & (g - r > 40))


def blue(r: np.ndarray, g: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Army map, 100 µg/ft² shading."""
    return (b > 150) & (r < 120) & (g < 140)


def cyan(r: np.ndarray, g: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Army map, 0.18 µg/m³ air shading."""
    return (r < 150) & (g > 190) & (b > 190)


def tracker_fields(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return the tracker map's lon, lat, final deposition and hourly mean air."""
    d = fs.load_map(path)
    g = d["grid"]
    lon = g["west"] + (np.arange(g["nx"]) + 0.5) / g["nx"] * (g["east"] - g["west"])
    lat = g["north"] - (np.arange(g["ny"]) + 0.5) / g["ny"] * (g["north"] - g["south"])
    return lon, lat, fs.field(d, "dep")[-1], fs.field(d, "m60")


def hysplit_fields(
    run: Path, scale: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[int, np.ndarray]]:
    """Return HYSPLIT's lon, lat, summed deposition and smoothed 0-10 m air by hour.

    Reads the con2asc files (cdump_*) that hysplit_stats.py writes. The air is smoothed
    by about 1 km for display only, to hide particle-counting noise at low levels.
    """
    lines = (run / "CONTROL").read_text().split("\n")
    i = next(k for k, line in enumerate(lines) if line.strip() == "cdump")
    clat, clon = map(float, lines[i - 4].split())
    dx = float(lines[i - 3].split()[0])
    span = [float(x) for x in lines[i - 2].split()]
    nlat, nlon = round(span[0] / dx) + 1, round(span[1] / dx) + 1
    lat = clat - span[0] / 2 + np.arange(nlat) * dx
    lon = clon - span[1] / 2 + np.arange(nlon) * dx
    dep = np.zeros((nlat, nlon))
    air: dict[int, np.ndarray] = {}
    for f in sorted(run.glob("cdump_*")):
        rows = f.read_text().splitlines()
        head = [c.strip() for c in rows[0].split(",")]
        v = np.array([[float(x) for x in row.split(",")] for row in rows[1:]])
        i10 = [k for k, c in enumerate(head) if c.startswith("P0") and c.endswith("00010")]
        i0 = [k for k, c in enumerate(head) if c.startswith("P0") and c.endswith("00000")]
        j = np.rint((v[:, 2] - lat[0]) / dx).astype(int)
        k = np.rint((v[:, 3] - lon[0]) / dx).astype(int)
        a = np.zeros((nlat, nlon))
        a[j, k] = v[:, i10].sum(1) * scale
        np.add.at(dep, (j, k), v[:, i0].sum(1) * scale)
        air[int(f.name[-2:]) - 15] = gaussian_filter(a, 2)
    return lon, lat, dep, air


def army(path: Path, src: tuple[int, int], sel: Mask) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Trace one shading of the Army map onto a lon-lat grid, placed from its source box."""
    a = np.asarray(Image.open(path).convert("RGB")).astype(int)[:560, 230:950]
    ys, xs = np.nonzero(sel(a[..., 0], a[..., 1], a[..., 2]))
    la = LAT0 - (ys - src[1]) / PX_PER_MI * DEG_LAT_PER_MI
    lo = LON0 + (xs + 230 - src[0]) / PX_PER_MI * DEG_LON_PER_MI
    glat = np.arange(39.0, 41.3, ARMY_CELL)
    glon = np.arange(-94.0, -90.5, ARMY_CELL)
    r = np.zeros((len(glat), len(glon)), dtype=bool)
    r[
        np.clip(((la - glat[0]) / ARMY_CELL).astype(int), 0, len(glat) - 1),
        np.clip(((lo - glon[0]) / ARMY_CELL).astype(int), 0, len(glon) - 1),
    ] = True
    return glon, glat, binary_closing(r, iterations=2).astype(float)


def base(ax: Axes, ext: tuple[float, float, float, float]) -> None:
    """Set the extent and aspect, and draw the plant and the listed towns."""
    ax.set_xlim(ext[0], ext[1])
    ax.set_ylim(ext[2], ext[3])
    ax.set_aspect(1 / math.cos(math.radians(LAT0)))
    ax.grid(lw=0.3, color="0.88")
    for name, la, lo in fs.TOWNS:
        short = name.split(",")[0]
        if short in TOWNS and ext[2] < la < ext[3] and ext[0] < lo < ext[1]:
            ax.plot(lo, la, "o", ms=2.5, color="0.35", zorder=5)
            ax.annotate(
                short, (lo, la), fontsize=7, color="0.3", xytext=(3, 2), textcoords="offset points"
            )
    ax.plot(LON0, LAT0, marker="*", ms=13, color="k", zorder=6)
    ax.set_xlabel("Longitude (°)")


def draw(args: list[str]) -> None:
    """Draw and save the two-panel figure."""
    case, scale_s, out, mapfile, run, army_air, army_dep = args
    tlon, tlat, tdep, tair = tracker_fields(Path(mapfile))
    hlon, hlat, hdep, hair = hysplit_fields(Path(run), float(scale_s))
    fig, axes = plt.subplots(
        1, 2, figsize=(13, 6.4), gridspec_kw={"width_ratios": [1, 1.25]}, constrained_layout=True
    )
    ax = axes[0]
    base(ax, (-92.0, -91.0, 40.40, 41.00))
    ax.set_ylabel("Latitude (°)")
    ax.set_title("Lead on the ground after 8 hours", fontsize=11)
    glon, glat, r5 = army(
        Path(army_dep), ARMY_DEP_SOURCE, lambda r, g, b: green(r, g, b) | blue(r, g, b)
    )
    _, _, r100 = army(Path(army_dep), ARMY_DEP_SOURCE, blue)
    ax.contourf(glon, glat, r5, [0.5, 2], colors=[C_AR], alpha=0.18)
    ax.contour(glon, glat, r5, [0.5], colors=C_AR, linewidths=1.3)
    ax.contour(glon, glat, r100, [0.5], colors=C_AR, linewidths=1.3, linestyles="--")
    for lon, lat, dep, color in ((tlon, tlat, tdep, C_TR), (hlon, hlat, hdep, C_HY)):
        ax.contour(lon, lat, dep, [5 * UG], colors=color, linewidths=1.5)
        ax.contour(lon, lat, dep, [100 * UG], colors=color, linewidths=1.5, linestyles="--")
    handles: list[Any] = [
        Line2D([], [], color=C_TR, label="Tracker (8:36 a.m. forecast)"),
        Line2D([], [], color=C_HY, label="HYSPLIT (9 a.m. analysis held)"),
        Line2D([], [], color=C_AR, label="Army map (digitized)"),
        Line2D([], [], color="0.3", label="5 µg/ft²"),
        Line2D([], [], color="0.3", ls="--", label="100 µg/ft²"),
    ]
    ax.legend(handles=handles, fontsize=7.5, loc="upper left")

    ax = axes[1]
    base(ax, (-93.4, -91.0, 39.45, 41.00))
    ax.set_title("Lead in the air ≥ 0.18 µg/m³ at about +1, +4 and +8 hours", fontsize=11)
    glon, glat, ra = army(Path(army_air), ARMY_AIR_SOURCE, cyan)
    ax.contourf(glon, glat, ra, [0.5, 2], colors=[C_AR], alpha=0.25)
    ax.contour(glon, glat, ra, [0.5], colors=C_AR, linewidths=1.1)
    for h, ls in ((1, ":"), (4, "--"), (8, "-")):
        ax.contour(tlon, tlat, tair[h - 1], [0.18e-9], colors=C_TR, linewidths=1.4, linestyles=ls)
        ax.contour(hlon, hlat, hair[h], [0.18e-9], colors=C_HY, linewidths=1.4, linestyles=ls)
    handles = [
        Line2D([], [], color=C_TR, label="Tracker, hour-mean at ground"),
        Line2D([], [], color=C_HY, label="HYSPLIT, hour-mean 0–10 m"),  # noqa: RUF001
        Line2D([], [], color=C_AR, lw=6, alpha=0.4, label="Army map (+1, +4, +8 h)"),
        Line2D([], [], color="0.3", ls=":", label="hour 1"),
        Line2D([], [], color="0.3", ls="--", label="hour 4"),
        Line2D([], [], color="0.3", label="hour 8"),
    ]
    ax.legend(handles=handles, fontsize=7.5, loc="lower right")
    if case == "mid":
        share = "26% of the lead airborne (the Army's mitigated case)"
    else:
        share = "100% of the lead airborne (EPA permit case)"
    fig.suptitle(f"Nov. 25, 2026, 9 a.m. CST detonation: {share}", fontsize=12)
    fig.savefig(out, dpi=160)


if __name__ == "__main__":
    draw(sys.argv[1:])
