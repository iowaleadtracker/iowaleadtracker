"""Shared readers and measures for the comparison scripts.

Both models are put on regular latitude-longitude grids so the same measures apply:
the tracker's map payload (``Tracker``) and a HYSPLIT run directory (``Hysplit``).
Hour ``h`` (1-based) is the clock hour ending ``h`` hours after the release.

Tracker fields used (``dispersal/grid.py``): ``conc`` the clock-hour mean at the ground,
``snap`` the field at the end of the hour, ``dep`` cumulative deposition. Its ``m60``
field is the highest running 60-minute mean reached in each hour, an envelope, and is
not an hourly mean.
"""

from __future__ import annotations

import math
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import forecast_summary as fs

if TYPE_CHECKING:
    from numpy.typing import ArrayLike

LAT0, LON0 = 40.825518, -91.266502
KM_PER_DEG = 111.195
KM_PER_MI = 1.609344
KG_PER_LB = 0.45359237
UG_FT2 = fs.KG_M2_PER_UG_FT2  # kg/m2 per µg/ft²
ARMY_AIR = 0.18e-9  # kg/m3, the Army map's air line
PAC1 = fs.PAC1_KG_M3
RELEASE_HOUR_UTC = 15


def dist_brg(lat: ArrayLike, lon: ArrayLike) -> tuple[np.ndarray, np.ndarray]:
    """Return miles and bearing (degrees from north) from the plant, flat-Earth."""
    dy = (np.asarray(lat) - LAT0) * KM_PER_DEG
    dx = (np.asarray(lon) - LON0) * KM_PER_DEG * math.cos(math.radians(LAT0))
    return np.hypot(dx, dy) / KM_PER_MI, (np.degrees(np.arctan2(dx, dy)) + 360) % 360


@dataclass
class Fields:
    """One model's output on a regular grid: 1-D lat and lon, 2-D fields by hour."""

    lat: np.ndarray  # ascending
    lon: np.ndarray  # ascending
    air: dict[int, np.ndarray]  # hour -> clock-hour mean near the ground (kg/m3)
    dep: dict[int, np.ndarray]  # hour -> cumulative deposition (kg/m2)
    snap: dict[int, np.ndarray]  # hour -> air at the end of the hour (tracker only)
    cell_mi2: np.ndarray  # area of each cell, by latitude row (sq mi)
    released_kg: float

    def mesh(self) -> tuple[np.ndarray, np.ndarray]:
        """Return 2-D latitude and longitude of cell centers."""
        lo, la = np.meshgrid(self.lon, self.lat)
        return la, lo

    def at(self, field: np.ndarray, lat: float, lon: float, radius_km: float = 0.0) -> float:
        """Return the field at a point, or its highest value within ``radius_km``."""
        la, lo = self.mesh()
        d = np.hypot((la - lat) * KM_PER_DEG, (lo - lon) * KM_PER_DEG * math.cos(math.radians(lat)))
        if radius_km:
            return float(field[d <= radius_km].max())
        return float(field.flat[int(np.argmin(d))])


def tracker(path: Path, scale: float = 1.0) -> Fields:
    """Read a tracker map page. ``scale`` multiplies the fields (the model is linear)."""
    d = fs.load_map(path)
    g = d["grid"]
    lon = g["west"] + (np.arange(g["nx"]) + 0.5) / g["nx"] * (g["east"] - g["west"])
    lat = g["north"] - (np.arange(g["ny"]) + 0.5) / g["ny"] * (g["north"] - g["south"])
    conc, snap, dep = (fs.field(d, n)[:, ::-1, :] * scale for n in ("conc", "snap", "dep"))
    hours = range(1, len(conc) + 1)
    cell = np.full(len(lat), (g["dx"] / 1000 / KM_PER_MI) ** 2)
    return Fields(
        lat=lat[::-1],
        lon=lon,
        air={h: conc[h - 1] for h in hours},
        dep={h: dep[h - 1] for h in hours},
        snap={h: snap[h - 1] for h in hours},
        cell_mi2=cell,
        released_kg=d["meta"]["releaseMass"] * scale,
    )


def hysplit(run: Path, scale: float = 1.0, level: str = "00010") -> Fields:
    """Read a HYSPLIT run directory (CONTROL and cdump). Air is the 0-10 m layer.

    Dumps the cdump with HYSPLIT's ``con2asc`` (needs ``HYSPLIT_DIR``). The CONTROL
    releases 100% of the lead; ``scale`` 0.26 gives the Army's case.
    """
    lines = (run / "CONTROL").read_text().split("\n")
    i = next(k for k, line in enumerate(lines) if line.strip() == "cdump")
    clat, clon = (float(x) for x in lines[i - 4].split())
    dx = float(lines[i - 3].split()[0])
    span = [float(x) for x in lines[i - 2].split()]
    nlat, nlon = round(span[0] / dx) + 1, round(span[1] / dx) + 1
    lat = clat - span[0] / 2 + np.arange(nlat) * dx
    lon = clon - span[1] / 2 + np.arange(nlon) * dx
    n_src = int(lines[1])
    n_met = int(lines[5 + n_src])
    k0 = 6 + n_src + 2 * n_met
    n_pol = int(lines[k0])
    released = sum(
        float(lines[k0 + 2 + 4 * p]) * float(lines[k0 + 3 + 4 * p]) for p in range(n_pol)
    )
    for f in run.glob("cdump_*"):
        f.unlink()
    exe = Path(os.environ["HYSPLIT_DIR"]) / "exec" / "con2asc"
    subprocess.run([str(exe), "-icdump", "-d", "-x"], cwd=run, check=True, capture_output=True)  # noqa: S603
    air: dict[int, np.ndarray] = {}
    dep: dict[int, np.ndarray] = {}
    total = np.zeros((nlat, nlon))
    for f in sorted(run.glob("cdump_*")):
        rows = f.read_text().splitlines()
        head = [c.strip() for c in rows[0].split(",")]
        v = np.array([[float(x) for x in row.split(",")] for row in rows[1:]]).reshape(
            -1, len(head)
        )
        ia = [k for k, c in enumerate(head) if c.startswith("P0") and c.endswith(level)]
        i0 = [k for k, c in enumerate(head) if c.startswith("P0") and c.endswith("00000")]
        j = np.rint((v[:, 2] - lat[0]) / dx).astype(int)
        k = np.rint((v[:, 3] - lon[0]) / dx).astype(int)
        a = np.zeros((nlat, nlon))
        a[j, k] = v[:, ia].sum(1) * scale
        np.add.at(total, (j, k), v[:, i0].sum(1) * scale)
        h = int(f.name[-2:]) - RELEASE_HOUR_UTC
        air[h], dep[h] = a, total.copy()
    cell = (dx * KM_PER_DEG / KM_PER_MI) ** 2 * np.cos(np.radians(lat))
    return Fields(
        lat=lat, lon=lon, air=air, dep=dep, snap={}, cell_mi2=cell, released_kg=released * scale
    )


def zone(f: Fields, field: np.ndarray, threshold: float) -> dict[str, float]:
    """Return area (sq mi), nearest and farthest distance (mi) and far-end bearing."""
    m = field >= threshold
    if not m.any():
        return {"area_mi2": 0.0, "near_mi": 0.0, "reach_mi": 0.0, "far_bearing": 0.0}
    la, lo = f.mesh()
    d, b = dist_brg(la[m], lo[m])
    i = int(np.argmax(d))
    area = float((m * f.cell_mi2[:, None]).sum())
    return {
        "area_mi2": area,
        "near_mi": float(d.min()),
        "reach_mi": float(d[i]),
        "far_bearing": float(b[i]),
    }


def center(f: Fields, field: np.ndarray) -> dict[str, float]:
    """Return the field-weighted center as miles and bearing from the plant."""
    la, lo = f.mesh()
    w = field * f.cell_mi2[:, None]
    if not w.sum():
        return {"center_mi": 0.0, "center_bearing": 0.0}
    d, b = dist_brg((w * la).sum() / w.sum(), (w * lo).sum() / w.sum())
    return {"center_mi": float(d), "center_bearing": float(b)}


def deposited_lb(f: Fields, hour: int) -> float:
    """Return the lead on the ground after ``hour`` hours (lb)."""
    m2 = f.cell_mi2[:, None] * (KM_PER_MI * 1000) ** 2
    return float((f.dep[hour] * m2).sum() / KG_PER_LB)


def arc_max(f: Fields, field: np.ndarray, lo_mi: float, hi_mi: float) -> float:
    """Return the highest value between two distances from the plant."""
    la, lo = f.mesh()
    d, _ = dist_brg(la, lo)
    m = (d >= lo_mi) & (d < hi_mi)
    return float(field[m].max()) if m.any() else 0.0


def overlap(
    a: Fields, fa: np.ndarray, b: Fields, fb: np.ndarray, threshold: float
) -> dict[str, float]:
    """Return overlap of two models' zones on a common 0.005 degree grid.

    Each model's zone is sampled at the common grid's cell centers (nearest cell).
    ``iou`` is intersection over union; ``a_in_b`` the share of A's zone inside B's.
    """
    step = 0.005
    lat = np.arange(min(a.lat[0], b.lat[0]), max(a.lat[-1], b.lat[-1]), step)
    lon = np.arange(min(a.lon[0], b.lon[0]), max(a.lon[-1], b.lon[-1]), step)

    def sample(f: Fields, field: np.ndarray) -> np.ndarray:
        j = np.rint((lat - f.lat[0]) / (f.lat[1] - f.lat[0])).astype(int)
        k = np.rint((lon - f.lon[0]) / (f.lon[1] - f.lon[0])).astype(int)
        ok = ((j >= 0) & (j < len(f.lat)))[:, None] & ((k >= 0) & (k < len(f.lon)))[None, :]
        out = field[np.clip(j, 0, len(f.lat) - 1)][:, np.clip(k, 0, len(f.lon) - 1)] >= threshold
        return np.asarray(out & ok)

    ma, mb = sample(a, fa), sample(b, fb)
    w = ((step * KM_PER_DEG / KM_PER_MI) ** 2 * np.cos(np.radians(lat)))[:, None]
    inter, union = float(((ma & mb) * w).sum()), float(((ma | mb) * w).sum())
    area_a, area_b = float((ma * w).sum()), float((mb * w).sum())
    return {
        "intersection_mi2": inter,
        "iou": inter / union if union else 0.0,
        "a_in_b": inter / area_a if area_a else 0.0,
        "b_in_a": inter / area_b if area_b else 0.0,
    }
