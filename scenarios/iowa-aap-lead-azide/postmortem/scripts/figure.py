"""Draw the six figures of the first comparison.

Usage (from the repository root, ``HYSPLIT_DIR`` set)::

    python figure.py FORECAST_MAPS ANALYSIS_MAPS HYSPLIT_RUN ARMY_DIR EPA_DIR COVERAGE.json \
        FORECAST_CACHE ANALYSIS_CACHE OUT_DIR

Figures 1, 2 and 4 are maps for the 26% case (the Army's emission factor): lead on the
ground, hourly mean air, and end-of-hour snapshots against the Army's final air map. Figure 3 is
the air at EPA's four real-time monitors, readings against the 7% (lowest) case. Figure 5 is the
direction sweep from ``monitor_coverage.py``. Figure 6 charts the numbers ``snapshots.py``
and ``army_map.py`` saved next to COVERAGE.json: how far out and in what direction each
source has the cloud at the Army map's four time marks. Every map shows EPA's 43 sampling sites; the
four with public readings are labeled.

One color per source throughout: tracker forecast, tracker on analyzed weather, HYSPLIT
on NOAA ARL's archived HRRR, and the Army's map. The palette passed the dataviz skill's
validator (color-vision separation); the legend and the paper's tables carry the same
information without color.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import math
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import army_map
import lib
import matplotlib as mpl
import snapshots

mpl.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from scipy.ndimage import gaussian_filter

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

C = {"forecast": "#f47230", "analysis": "#257de0", "hysplit": "#6a4ce2", "army": "#00b894"}
NAMES = {
    "forecast": "Tracker, forecast shown at 9 a.m.",
    "analysis": "Tracker, analyzed weather",
    "hysplit": "HYSPLIT, NOAA ARL archived weather",
    "army": "Army map (final, 7 a.m. Nov. 25)",
}
INK, MUTED = "#191919", "#666666"
TOWNS = {
    "Middletown", "Burlington", "West Point", "Fort Madison", "Donnellson", "Keokuk", "Kahoka",
    "Canton", "Quincy", "Palmyra", "Hannibal", "Mount Pleasant", "Farmington", "Memphis",
}  # fmt: skip
CASE, SCALE = "mid", 0.26
ARMY_MAP = "final"
LOW_SCALE = 0.07
FLOOR = 1e-4  # µg/m³, where zero readings and zero predictions are drawn in figure 3
MI_PER_DEG_LAT = lib.KM_PER_DEG / lib.KM_PER_MI
HOUR_LABEL = {1: "9 to 10 a.m.", 2: "10 to 11 a.m.", 3: "11 a.m. to noon", 4: "noon to 1 p.m."}
WIDE_MAP_DEG = 2
STAMP = "Iowa Lead Tracker (iowaleadtracker.com) \u00b7 Preliminary analysis, pending peer review"
STAMP_NOTE = "Unofficial analysis, not from the Army or any government agency"
STAMP_BAND = 0.045  # share of the figure height kept for the source line
Sites = tuple[list[dict[str, Any]], dict[str, tuple[float, float]]]
Readings = dict[str, list[tuple[dt.datetime, float]]]


def sites(epa: Path) -> tuple[Sites, Readings]:
    """Return EPA's sampling sites, the monitors' positions and their readings."""
    with (epa / "epa_air_stations.csv").open() as f:
        all_sites = list(csv.DictReader(f))
    readings: Readings = {}
    pos: dict[str, tuple[float, float]] = {}
    with (epa / "epa_xact_public_viewer.csv").open() as f:
        for r in csv.DictReader(f):
            t = dt.datetime.strptime(r["time_utc"], "%Y-%m-%d %H:%M").replace(
                tzinfo=dt.timezone.utc
            )
            readings.setdefault(r["station_id"], []).append((t, float(r["concentration"])))
            pos[r["station_id"]] = (float(r["lat"]), float(r["lon"]))
    return (all_sites, pos), readings


def base(ax: Axes, ext: tuple[float, float, float, float], epa: Sites) -> None:
    """Set up a map panel: extent, towns, plant, scale bar and EPA's sites."""
    ax.set_xlim(ext[0], ext[1])
    ax.set_ylim(ext[2], ext[3])
    ax.set_aspect(1 / math.cos(math.radians(lib.LAT0)))
    ax.tick_params(labelsize=7, colors=MUTED)
    for s in ax.spines.values():
        s.set_color("#cccccc")
    ax.grid(lw=0.3, color="#e6e6e6")

    def inside(la: float, lo: float) -> bool:
        return ext[2] < la < ext[3] and ext[0] < lo < ext[1]

    for name, la, lo in lib.fs.TOWNS:
        short = name.split(",")[0]
        if short in TOWNS and inside(la, lo):
            ax.plot(lo, la, "o", ms=2, color="#999999", zorder=3)
            ax.annotate(
                short,
                (lo, la),
                fontsize=6.5,
                color=MUTED,
                xytext=(3, 2),
                textcoords="offset points",
            )
    for s in epa[0]:
        if inside(float(s["lat"]), float(s["lon"])):
            ax.plot(
                float(s["lon"]), float(s["lat"]), "s", ms=3, mfc="none", mec=INK, mew=0.6, zorder=6
            )
    for name, (la, lo) in epa[1].items():
        if inside(la, lo):
            ax.plot(lo, la, "D", ms=6, mfc=INK, mec="white", mew=1, zorder=8)
            if ext[1] - ext[0] >= WIDE_MAP_DEG:
                continue
            ax.annotate(
                name,
                (lo, la),
                fontsize=7,
                color=INK,
                weight="bold",
                xytext=(5, -9),
                textcoords="offset points",
                zorder=9,
            )
    ax.plot(lib.LON0, lib.LAT0, marker="*", ms=13, mfc=INK, mec="white", mew=0.8, zorder=9)
    miles = 10 if ext[1] - ext[0] < WIDE_MAP_DEG else 25
    x0, y0 = ext[0] + 0.04 * (ext[1] - ext[0]), ext[2] + 0.05 * (ext[3] - ext[2])
    dlon = miles / (MI_PER_DEG_LAT * math.cos(math.radians(lib.LAT0)))
    ax.plot([x0, x0 + dlon], [y0, y0], color=INK, lw=2, solid_capstyle="butt", zorder=9)
    ax.annotate(
        f"{miles} miles", (x0, y0), fontsize=7, color=INK, xytext=(0, 4), textcoords="offset points"
    )


def outline(
    ax: Axes,
    f: lib.Fields,
    field: np.ndarray,
    level: float,
    key: str,
    *,
    fill: bool = False,
    smooth: float = 0,
) -> None:
    """Draw one source's zone outline."""
    z = gaussian_filter(field, smooth) if smooth else field
    if z.max() < level:
        return
    if fill:
        ax.contourf(f.lon, f.lat, z, [level, np.inf], colors=[C[key]], alpha=0.16, zorder=4)
    ax.contour(f.lon, f.lat, z, [level], colors=C[key], linewidths=2, zorder=5)


def legend(
    ax: Axes, keys: list[str], notes: dict[str, str] | None = None, loc: str = "upper left"
) -> None:
    """Legend: one entry per source, plus the EPA markers and the plant."""
    notes = notes or {}
    h: list[Any] = [
        Line2D([], [], color=C[k], lw=2, label=NAMES[k] + notes.get(k, ""))
        for k in keys
        if k != "army"
    ]
    if "army" in keys:
        h.append(
            Patch(
                fc=C["army"], ec=C["army"], alpha=0.5, label=NAMES["army"] + notes.get("army", "")
            )
        )
    h += [
        Line2D(
            [],
            [],
            marker="D",
            ls="",
            mfc=INK,
            mec="white",
            ms=6,
            label="EPA real-time lead monitor",
        ),
        Line2D(
            [],
            [],
            marker="s",
            ls="",
            mfc="none",
            mec=INK,
            ms=4,
            label="EPA sampling site, no results posted",
        ),
        Line2D([], [], marker="*", ls="", mfc=INK, mec="white", ms=11, label="Detonation site"),
    ]
    ax.legend(handles=h, fontsize=7, loc=loc, framealpha=0.95, edgecolor="#cccccc")


def title(fig: Figure, text: str) -> None:
    """Left-aligned figure title, and the source line along the bottom of every figure."""
    fig.suptitle(text, fontsize=11, color=INK, x=0.01, ha="left")
    engine = fig.get_layout_engine()
    if engine is not None:
        engine.set(rect=(0, STAMP_BAND, 1, 1 - STAMP_BAND))  # keep the bottom band clear
    fig.text(0.01, 0.012, STAMP, fontsize=8.5, color=INK, weight="bold", ha="left", va="bottom")
    fig.text(0.99, 0.012, STAMP_NOTE, fontsize=8, color=MUTED, ha="right", va="bottom")


def fig_ground(
    runs: dict[str, lib.Fields], army: dict[str, lib.Fields], epa: Sites, n: int, out: Path
) -> None:
    """Figure 1: lead on the ground, 5 and 100 µg/ft², in two panels."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.9), constrained_layout=True)
    panels = (
        (axes[0], 5, "5 µg/ft² or more", (-92.0, -90.95, 40.33, 40.98), "army5"),
        (axes[1], 100, "100 µg/ft² or more", (-91.62, -91.12, 40.62, 40.90), "army100"),
    )
    for ax, level, name, ext, akey in panels:
        base(ax, ext, epa)
        outline(ax, army[akey], army[akey].dep[0], 0.5, "army", fill=True)
        outline(ax, runs["forecast"], runs["forecast"].dep[8], level * lib.UG_FT2, "forecast")
        outline(ax, runs["analysis"], runs["analysis"].dep[8], level * lib.UG_FT2, "analysis")
        outline(ax, runs["hysplit"], runs["hysplit"].dep[n], level * lib.UG_FT2, "hysplit")
        ax.set_title(f"Modeled lead on the ground: {name}", fontsize=10, color=INK, loc="left")
    legend(
        axes[0], ["forecast", "analysis", "hysplit", "army"], {"hysplit": f" (first {n} h only)"}
    )
    title(
        fig,
        "Model estimates if 26% of the lead became airborne as fine dust. "
        "These are not measurements.",
    )
    fig.savefig(out, dpi=160)
    plt.close(fig)


def fig_air(runs: dict[str, lib.Fields], epa: Sites, hours: list[int], out: Path) -> None:
    """Figure 2: hourly mean air at or above 0.18 µg/m³, one panel per hour."""
    fig, axes = plt.subplots(
        1, len(hours), figsize=(6.5 * len(hours), 5.6), constrained_layout=True, squeeze=False
    )
    for ax, h in zip(axes[0], hours, strict=True):
        base(ax, (-92.35, -90.95, 40.05, 40.98), epa)
        for key in ("forecast", "analysis", "hysplit"):
            outline(
                ax,
                runs[key],
                runs[key].air[h],
                lib.ARMY_AIR,
                key,
                smooth=2 if key == "hysplit" else 0,
            )
        ax.set_title(f"Hour {h}: {HOUR_LABEL[h]} CST", fontsize=10, color=INK, loc="left")
    legend(axes[0][0], ["forecast", "analysis", "hysplit"], loc="lower right")
    title(
        fig,
        "Modeled hourly mean lead in air at the ground, 0.18 µg/m³ or more, 26% case. "
        "These are not measurements.",
    )
    fig.savefig(out, dpi=160)
    plt.close(fig)


def fig_snap(
    snaps: dict[str, snapshots.Snaps],
    path: lib.Fields,
    marks: dict[str, dict[str, float]],
    epa: Sites,
    out: Path,
) -> None:
    """Figure 4: the cloud at the Army map's four time marks, against its path and marks."""
    fig, axes = plt.subplots(2, 2, figsize=(13, 10.5), constrained_layout=True)
    exts = {
        "0.5": (-91.62, -91.12, 40.62, 40.90),
        "2": (-92.1, -91.0, 40.25, 40.95),
        "3": (-92.4, -91.0, 40.05, 40.95),
        "5": (-93.0, -91.0, 39.65, 40.95),
    }
    for ax, (mark, ext) in zip(axes.flat, exts.items(), strict=True):
        base(ax, ext, epa)
        outline(ax, path, path.dep[0], 0.5, "army", fill=True)
        for key in ("forecast", "analysis", "hysplit"):
            if mark in snaps[key]:
                f, field = snaps[key][mark]
                smooth = 2 if key == "hysplit" else 0
                outline(ax, f, field, lib.ARMY_AIR, key, smooth=smooth)
        m = marks[mark]
        ax.plot(m["lon"], m["lat"], "o", ms=9, mfc="white", mec=C["army"], mew=2.5, zorder=7)
        ax.annotate(
            f"Army T+{mark}", (m["lon"], m["lat"]), fontsize=7.5, color=INK, weight="bold",
            xytext=(-8, 8), textcoords="offset points", ha="right", zorder=9,
        )  # fmt: skip
        when = "30 minutes" if mark == "0.5" else f"{mark} hours"
        note = "" if mark in snaps["hysplit"] else " (HYSPLIT's archived weather ends at 2 hours)"
        ax.set_title(f"{when} after the detonation{note}", fontsize=10, color=INK, loc="left")
    legend(axes[0][1], ["forecast", "analysis", "hysplit", "army"], {"army": ": cloud path"})
    title(
        fig,
        "Modeled lead in air at one moment, 0.18 µg/m³ or more, 26% case, "
        "with the cloud path and time marks from the Army's final map.",
    )
    fig.savefig(out, dpi=160)
    plt.close(fig)


def fig_monitors(
    low: dict[str, lib.Fields], epa: Sites, readings: Readings, hours: list[int], out: Path
) -> None:
    """Figure 3: EPA's readings against the lowest case's hourly means at each monitor."""
    cst = dt.timezone(dt.timedelta(hours=-6))
    t0 = dt.datetime(2026, 11, 25, 9, tzinfo=cst)
    fig, axes = plt.subplots(1, 4, figsize=(15, 4.3), constrained_layout=True, sharey=True)
    for ax, (name, rows) in zip(axes, sorted(readings.items()), strict=True):
        la, lo = epa[1][name]
        d, b = lib.dist_brg(la, lo)
        x = [(t.astimezone(cst) - t0).total_seconds() / 3600 for t, _ in rows]
        y = [max(v, FLOOR) for _, v in rows]
        ax.axvline(0, color="#999999", lw=1, ls=(0, (2, 2)))
        for k, key in enumerate(("forecast", "analysis", "hysplit")):
            f = low[key]
            for h in hours:
                v = max(f.at(f.air[h], la, lo) * 1e9, FLOOR)
                ax.plot(
                    [h - 1, h],
                    [v, v],
                    color=C[key],
                    lw=7 - 2.5 * k,
                    solid_capstyle="butt",
                    zorder=4 + k,
                    path_effects=[
                        pe.Stroke(linewidth=8.5 - 2.5 * k, foreground="white"),
                        pe.Normal(),
                    ],
                )
        ax.plot(x, y, "o", ms=3.2, mfc=INK, mec="white", mew=0.4, zorder=8)
        ax.set_yscale("log")
        ax.set_ylim(FLOOR / 2, 100)
        last = math.ceil(max(x))
        ax.set_xlim(-2, last)
        ax.set_xticks(range(-2, last + 1))
        ax.set_xticklabels([f"{(9 + k - 1) % 12 + 1}" for k in range(-2, last + 1)])
        ax.tick_params(labelsize=7, colors=MUTED)
        ax.grid(lw=0.3, color="#e6e6e6")
        for s in ax.spines.values():
            s.set_color("#cccccc")
        ax.set_title(
            f"{name}: {float(d):.1f} miles out, bearing {float(b):.0f}°",
            fontsize=10,
            color=INK,
            loc="left",
        )
        ax.set_xlabel("Hour of Nov. 25 (CST)", fontsize=8, color=MUTED)
    axes[0].set_ylabel("Lead in air, µg/m³ (log scale)", fontsize=8, color=MUTED)
    axes[0].set_yticks([FLOOR, 1e-3, 1e-2, 1e-1, 1, 10, 100])
    axes[0].set_yticklabels(["0", "0.001", "0.01", "0.1", "1", "10", "100"])
    axes[0].annotate(
        "detonation", (0, 40), fontsize=7, color=MUTED, xytext=(3, 0), textcoords="offset points"
    )
    keys: list[Any] = [
        Line2D(
            [], [], marker="o", ls="", mfc=INK, mec="white", ms=5, label="EPA reading, as posted"
        )
    ]
    keys += [
        Line2D([], [], color=C[k], lw=7 - 2.5 * i, label=NAMES[k])
        for i, k in enumerate(("forecast", "analysis", "hysplit"))
    ]
    axes[3].legend(
        handles=keys, fontsize=7, loc="upper right", framealpha=0.95, edgecolor="#cccccc"
    )
    title(
        fig,
        "Lead in air at EPA's four real-time monitors: readings, and the models' hourly means "
        "for their lowest case (7% airborne)",
    )
    fig.savefig(out, dpi=160)
    plt.close(fig)


def fig_coverage(cov: dict[str, Any], out: Path) -> None:
    """Figure 5: what the best-placed real-time monitor would read, by cloud direction."""
    fig, ax = plt.subplots(figsize=(10, 5.2), constrained_layout=True)
    keys = {
        "forecast": "tracker forecast",
        "analysis": "tracker analysis",
        "hysplit": "hysplit analysis",
    }
    for k, (key, run) in enumerate(keys.items()):
        sweep = cov["runs"][run]["sweep"]
        x = [p["cloud_bearing"] for p in sweep]
        y = [max(p["air_100pct_ugm3"] * LOW_SCALE, FLOOR) for p in sweep]
        ax.plot(x, y, color=C[key], lw=2, zorder=4 + k)
        own = cov["runs"][run]["cloud_bearing_hour1"]
        ax.plot(
            own,
            max(sweep[len(sweep) // 2]["air_100pct_ugm3"] * LOW_SCALE, FLOOR),
            "o",
            ms=8,
            mfc=C[key],
            mec="white",
            mew=1.5,
            zorder=8,
        )
    for level, text in (
        (0.18, "0.18: the Army map's air line"),
        (0.01, "0.01: highest reading any monitor posted"),
    ):
        ax.axhline(level, color=MUTED, lw=1, ls=(0, (4, 3)), zorder=2)
        ax.annotate(
            text,
            (249.5, level),
            fontsize=7.5,
            color=MUTED,
            ha="right",
            va="bottom",
            xytext=(0, 2),
            textcoords="offset points",
        )
    ax.axvspan(204, 211, color="#e6e6e6", zorder=1)
    ax.annotate(
        "along the surface wind\n(stations, analysis)",
        (207.5, 60),
        fontsize=7.5,
        color=MUTED,
        ha="center",
    )
    ax.set_yscale("log")
    ax.set_ylim(FLOOR, 200)
    ax.set_xlim(198, 250)
    ax.set_yticks([FLOOR, 1e-3, 1e-2, 1e-1, 1, 10, 100])
    ax.set_yticklabels(["0", "0.001", "0.01", "0.1", "1", "10", "100"])
    ax.set_xlabel(
        "Direction the cloud travels in its first hour (degrees from north; 225° is southwest)",
        fontsize=8.5,
        color=MUTED,
    )
    ax.set_ylabel(
        "Highest hourly mean at any real-time monitor, µg/m³ (log scale)", fontsize=8.5, color=MUTED
    )
    ax.tick_params(labelsize=8, colors=MUTED)
    ax.grid(lw=0.3, color="#e6e6e6")
    for sp in ax.spines.values():
        sp.set_color("#cccccc")
    handles: list[Any] = [Line2D([], [], color=C[k], lw=2, label=NAMES[k]) for k in keys]
    handles.append(
        Line2D(
            [],
            [],
            marker="o",
            ls="",
            mfc=MUTED,
            mec="white",
            ms=8,
            label="each run's own direction",
        )
    )
    ax.legend(
        handles=handles, fontsize=7.5, loc="lower center", framealpha=0.95, edgecolor="#cccccc"
    )
    title(
        fig,
        "If the modeled cloud is turned to another direction, what would EPA's real-time "
        "monitors read? Lowest case (7% airborne).",
    )
    fig.savefig(out, dpi=160)
    plt.close(fig)


MARK_ROWS = (
    ("army", "Army map: mark on its path", "", True),
    ("forecast", "Tracker, forecast shown at 9 a.m.", "tracker forecast", True),
    ("analysis", "Tracker, analyzed weather", "tracker analysis", True),
    ("hysplit", "HYSPLIT, NOAA ARL archived weather", "hysplit archive", True),
    ("hysplit", "HYSPLIT, pressure-level analyses", "hysplit pressure levels", False),
)  # color, row label, key in snapshots.json, filled marker (hollow: the weaker weather input)


def _mark_panel(ax: Axes, hour: str, cut: dict[str, float], sn: dict[str, Any]) -> None:
    """One time mark of figure 6: each source's cloud as a range of distance, with its center."""
    ax.axvline(cut["miles"], color=C["army"], lw=1.2, zorder=1)
    ax.plot(cut["miles"], 0, "o", ms=9, mfc="white", mec=C["army"], mew=2.5, zorder=5)
    note = {"xytext": (7, 0), "textcoords": "offset points", "va": "center", "fontsize": 7.5}
    ax.annotate(f"{cut['miles']:.0f} mi", (cut["miles"], 0), color=INK, **note)
    far = cut["miles"]
    for row, (key, _, run, filled) in enumerate(MARK_ROWS):
        if not run:
            continue
        snap = sn[run].get(hour)
        if snap is None:
            ax.annotate(
                "not yet run", (0.04, row), xycoords=("axes fraction", "data"), color=MUTED, **note
            )
            continue
        near, reach, mid = snap["near_mi"], snap["reach_mi"], snap["center_mi"]
        far = max(far, reach)
        ax.plot([near, reach], [row, row], color=C[key], lw=7, alpha=0.3, solid_capstyle="butt")
        ax.plot(mid, row, "o", ms=8, mfc=C[key] if filled else "white", mec=C[key], mew=2, zorder=5)
        ax.annotate(f"center {mid:.0f} mi", (reach, row), color=INK, **note)
    ax.set_xlim(0, far * 1.5)
    ax.set_ylim(len(MARK_ROWS) - 0.4, -0.6)
    label = "30 minutes" if hour == "0.5" else f"{hour} hours"
    ax.set_title(f"{label} after the detonation", fontsize=9.5, color=INK, loc="left")
    ax.set_xlabel("Miles from the plant", fontsize=8, color=MUTED)
    ax.set_yticks(range(len(MARK_ROWS)))
    ax.tick_params(labelsize=8, colors=MUTED, length=0)
    ax.grid(axis="x", lw=0.3, color="#e6e6e6")
    for sp in ax.spines.values():
        sp.set_color("#cccccc")


def fig_marks(sn: dict[str, Any], army: dict[str, Any], epa: Sites, out: Path) -> None:
    """Figure 6: distance and direction of the cloud at the Army map's four time marks."""
    cuts = army["air_cuts"]
    fig = plt.figure(figsize=(12.5, 8.2), constrained_layout=True)
    grid = fig.add_gridspec(2, len(cuts), height_ratios=(1, 1.15))
    for k, (hour, cut) in enumerate(cuts.items()):
        ax = fig.add_subplot(grid[0, k])
        _mark_panel(ax, hour, cut, sn)
        ax.set_yticklabels([r[1] for r in MARK_ROWS] if k == 0 else [])
        for tick in ax.get_yticklabels():
            tick.set_color(INK)
    ax = fig.add_subplot(grid[1, :])
    hours = [float(h) for h in cuts]
    bearings = [lib.dist_brg(la, lo)[1] for la, lo in epa[1].values()]
    ax.axhspan(min(bearings), max(bearings), color="#ececec", zorder=1)
    ax.annotate(
        f"EPA's four real-time lead monitors lie at {min(bearings):.0f}°"
        f" to {max(bearings):.0f}° from the plant",
        (0.08, max(bearings)),
        fontsize=7.5,
        color=MUTED,
        va="top",
        xytext=(0, -4),
        textcoords="offset points",
    )
    path = army["air_path"]["axis_bearing"]
    ax.plot(hours, [path] * len(hours), color=C["army"], lw=2, zorder=3)
    ax.plot(hours, [path] * len(hours), "o", ms=9, mfc="white", mec=C["army"], mew=2.5, zorder=6)
    ends = {"army": (hours[-1], path, "Army map: its path", 0)}
    for key, name, run, filled in MARK_ROWS:
        if not run:
            continue
        x = [float(h) for h in sn[run] if h in cuts]
        y = [sn[run][h]["center_bearing"] for h in sn[run] if h in cuts]
        ax.plot(x, y, color=C[key], lw=2, ls="-" if filled else (0, (4, 2)), zorder=4)
        ax.plot(x, y, "o", ms=8, mfc=C[key] if filled else "white", mec=C[key], mew=2, zorder=6)
        ends[run] = (x[-1], y[-1], name, 11 if x[-1] < hours[-1] else 0)  # clear of other lines
    for end_x, end_y, name, lift in ends.values():
        ax.annotate(
            f"{name}, {end_y:.0f}°",
            (end_x, end_y),
            fontsize=7.5,
            color=INK,
            va="center",
            xytext=(9, lift),
            textcoords="offset points",
        )
    ax.set_xlim(0, hours[-1] + 1.9)
    ax.set_xticks(hours)
    ax.set_xticklabels(["30 min" if h < 1 else f"{h:g} hours" for h in hours])
    ax.set_ylim(210, 236)
    ax.set_title(
        "Direction from the plant to the center of the cloud at each time"
        " (degrees from north; 225° is southwest, larger is farther west)",
        fontsize=9.5,
        color=INK,
        loc="left",
    )
    ax.set_xlabel("Time after the detonation", fontsize=8, color=MUTED)
    ax.set_ylabel("Degrees", fontsize=8, color=MUTED)
    ax.tick_params(labelsize=8, colors=MUTED)
    ax.grid(lw=0.3, color="#e6e6e6")
    for sp in ax.spines.values():
        sp.set_color("#cccccc")
    title(
        fig,
        "Where each source has the cloud at the Army map's four time marks, 26% case. "
        "Bars: lead in air at the ground of 0.18 µg/m³ or more; dots: the cloud's center.",
    )
    fig.savefig(out, dpi=160)
    plt.close(fig)


def main(args: list[str]) -> None:
    """Read every source and draw the figures."""
    fc_dir, an_dir, hy_run, army_dir, epa_dir, cov_json, fc_cache, an_cache, out = (
        Path(a) for a in args
    )
    out.mkdir(parents=True, exist_ok=True)
    epa, readings = sites(epa_dir)
    runs = {
        "forecast": lib.tracker(fc_dir / f"{CASE}-0900.html"),
        "analysis": lib.tracker(an_dir / f"an_{CASE}.html"),
        "hysplit": lib.hysplit(hy_run, SCALE),
    }
    hours = sorted(runs["hysplit"].air)
    spec = army_map.MAPS[ARMY_MAP]
    tip, px = spec["tip"], spec["px_per_mi"]
    gm = army_map.masks(army_map.image(army_dir, "ground", ARMY_MAP), tip)
    air = army_map.masks(army_map.image(army_dir, "air", ARMY_MAP), tip)["air"]
    air = army_map.nearest_piece(air, tip)
    army = {
        "army5": army_map.to_fields(gm["dep5"], tip, px),
        "army100": army_map.to_fields(gm["dep100"], tip, px),
    }
    path = army_map.to_fields(air, army_map.air_anchor(ARMY_MAP, air), px)
    fig_ground(runs, army, epa, hours[-1], out / "fig1_ground.png")
    fig_air(runs, epa, hours, out / "fig2_air_hourly.png")
    snaps = {
        "forecast": snapshots.tracker_snaps(fc_cache),
        "analysis": snapshots.tracker_snaps(an_cache),
        "hysplit": snapshots.hysplit_snaps(hy_run),
    }
    fig_snap(snaps, path, army_map.cuts(ARMY_MAP, air), epa, out / "fig4_air_snapshots.png")
    fig_coverage(json.loads(cov_json.read_text()), out / "fig5_monitor_coverage.png")
    saved = {
        n: json.loads((cov_json.parent / f"{n}.json").read_text())
        for n in ("snapshots", "army_map")
    }
    fig_marks(saved["snapshots"], saved["army_map"][ARMY_MAP], epa, out / "fig6_time_marks.png")
    low = {
        "forecast": lib.tracker(fc_dir / "low-0900.html"),
        "analysis": lib.tracker(an_dir / "an_low.html"),
        "hysplit": lib.hysplit(hy_run, LOW_SCALE),
    }
    fig_monitors(low, epa, readings, hours, out / "fig3_epa_monitors.png")


if __name__ == "__main__":
    main(sys.argv[1:])
