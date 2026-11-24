#!/usr/bin/env python3
"""Crosswind spread sigma_y of each spread scheme against two tracer experiments.

    python3 tools/tracer_sigma_y.py          # Markdown tables, as in TURBULENCE.md

Data in ``tests/data/tracer/`` (see its README):

- Project Prairie Grass (Barad 1958): sigma_y per run and arc from J. S. Irwin's analysis
  (PGrassOBSAnalysis.txt) with u*, w*, L, mixing heights and wind from the AERMOD
  surface file of the ASTM D6589 archive (PGRSURF.MET); release 0.46 m, 10-minute
  samples, arcs 50-800 m.
- Project Sagebrush Phase 1 (Finn et al. 2015, 2016): second-moment sigma_y of each
  10-minute bag read from Fig. 212 of NOAA Tech. Memo OAR ARL-268, with the bag's
  10 m wind, u* and z/L (sonics R3, R4) and sigma_A class (Tables 19-23); release 1.5 m,
  arcs 200-3,200 m. Mixing heights are the mean radiosonde values of its Table 18.

Schemes: ``briggs`` (this model's original curves; Prairie Grass classes from L and z0,
which were not recorded), ``turbulence`` (:mod:`dispersal.turbulence`, stepped exactly as
in the model), and AERMOD's sigma_y formula (EPA 2026, Eq. 77) for reference.
"""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path
from typing import NamedTuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dispersal.constants import VON_KARMAN
from dispersal.dispersion import SY_C, SY_E, SY_K, briggs
from dispersal.turbulence import (
    AVERAGING_DEFAULT_MIN,
    SIGMA_V_MIN_DEFAULT,
    grow,
    sigma_vw,
)

DATA = Path(__file__).resolve().parents[1] / "tests" / "data" / "tracer"
SAGEBRUSH_ZI = {"1": 1250.0, "2": 1110.0, "3": 865.0, "4": 2030.0, "5": 1150.0}  # Table 18
AERMOD_ALPHA = 78.0  # EPA (2026), Eq. 78, near-surface release
AERMOD_P = 0.3  # EPA (2026), Eq. 77
STEP_S = 5.0  # growth step for the turbulence scheme, s
# Class-centre 1/L = a + b log10 z0 for classes A-F (after Golder 1972, as tabulated in
# Seinfeld and Pandis 2016); only for the Briggs class at Prairie Grass.
GOLDER = [(-0.096, 0.029), (-0.037, 0.029), (-0.002, 0.018), (0.0, 0.0), (0.004, -0.018)]
GOLDER += [(0.035, -0.036)]


class Case(NamedTuple):
    """One measured sigma_y and the weather it was measured in."""

    site: str
    group: str
    x: float  # m
    sigma_y: float  # m, measured
    u: float  # m/s, transport wind
    u_star: float
    w_star: float
    obukhov: float
    zi: float
    z_release: float
    cls: int  # Pasquill class 0-5 for the Briggs curves


def _golder_class(obukhov: float, z0: float) -> int:
    centres = np.array([a + b * math.log10(z0) for a, b in GOLDER])
    return int(np.argmin(np.abs(centres - 1.0 / obukhov)))


def load_prairie_grass() -> list[Case]:
    """Prairie Grass arcs with their AERMOD surface meteorology."""
    out = []
    with (DATA / "prairie_grass_sigma_y.csv").open() as f:
        for r in csv.DictReader(f):
            obukhov = float(r["obukhov_m"])
            out.append(
                Case(
                    "Prairie Grass",
                    r["run"],
                    float(r["x_m"]),
                    float(r["sigma_y_m"]),
                    float(r["u_ms"]),
                    float(r["u_star_ms"]),
                    float(r["w_star_ms"]),
                    obukhov,
                    max(float(r["zic_m"]), float(r["zim_m"])),
                    0.46,
                    _golder_class(obukhov, float(r["z0_m"])),
                )
            )
    return out


def _num(v: str) -> float:
    """Return a value, or the mean of two ("a|b") where two bags could not be told apart."""
    parts = [float(p) for p in v.split("|")]
    return sum(parts) / len(parts)


def load_sagebrush() -> list[Case]:
    """Sagebrush Phase 1 bags (10-minute sigma_y) with their sonic meteorology."""
    out = []
    with (DATA / "sagebrush1_sigma_y_10min.csv").open() as f:
        for r in csv.DictReader(f):
            u_star = (_num(r["ustar_R3"]) + _num(r["ustar_R4"])) / 2
            zl = (_num(r["zL_R3"]) + _num(r["zL_R4"])) / 2
            obukhov = 3.2 / zl  # sonics at 3.2 m
            zi = SAGEBRUSH_ZI[r["iop"]]
            w_star = max(-(u_star**3) * zi / (VON_KARMAN * obukhov), 0.0) ** (1 / 3)
            out.append(
                Case(
                    "Sagebrush",
                    r["iop"],
                    float(r["x_m"]),
                    float(r["sigma_y_m"]),
                    _num(r["U10_COC_ms"]),
                    u_star,
                    w_star,
                    obukhov,
                    zi,
                    1.5,
                    "ABCDEF".index(r["PG_sigA"]),
                )
            )
    return out


def sigma_y_briggs(c: Case) -> float:
    """Return the original Briggs rural curve for the case's class."""
    return float(briggs(SY_C[c.cls], SY_K[c.cls], SY_E[c.cls], c.x))


def sigma_y_turbulence(
    cases: list[Case],
    sigma_v_min: float = SIGMA_V_MIN_DEFAULT,
    averaging_min: float = AVERAGING_DEFAULT_MIN,
) -> list[float]:
    """sigma_y from :mod:`dispersal.turbulence`, grown step by step as in the model."""

    def col(name: str) -> np.ndarray:
        return np.array([getattr(c, name) for c in cases], float)

    obukhov = col("obukhov")
    sv, sw = sigma_vw(
        col("u_star"),
        obukhov,
        col("w_star"),
        col("z_release"),
        col("zi"),
        np.full(len(cases), 3),
        sigma_v_min,
    )
    t_total = col("x") / col("u")
    sy, sz, t = np.ones(len(cases)), np.ones(len(cases)), np.zeros(len(cases))
    while np.any(t < t_total - 1e-9):
        dt = np.clip(t_total - t, 0.0, STEP_S)
        sy, sz = grow(sy, sz, sv, sw, obukhov > 0, dt, averaging_min)
        t += dt
    return [float(v) for v in sy]


def sigma_y_aermod(c: Case) -> float:
    """Return AERMOD's sigma_y for a near-surface release (EPA 2026, Eqs. 38-41, 77-78)."""
    sv = max(math.sqrt(3.6 * c.u_star**2 + 0.35 * c.w_star**2), SIGMA_V_MIN_DEFAULT)
    x_dimless = sv * c.x / (c.u * c.zi)
    return float(sv * c.x / (c.u * (1 + AERMOD_ALPHA * x_dimless) ** AERMOD_P))


def score(pred: list[float], obs: list[float]) -> tuple[float, float]:
    """Geometric mean of predicted / observed, and the share within a factor of 2."""
    r = np.array(pred) / np.array(obs)
    return float(np.exp(np.mean(np.log(r)))), float(np.mean((r >= 0.5) & (r <= 2.0)))


def table(cases: list[Case], by: str) -> list[str]:
    """Markdown rows: all cases, then one row per distance (``by="x"``) or per test."""
    preds = {
        "Briggs (original)": [sigma_y_briggs(c) for c in cases],
        "Turbulence, 10-min (default)": sigma_y_turbulence(cases),
        "Turbulence, 60-min": sigma_y_turbulence(cases, averaging_min=60.0),
        "AERMOD": [sigma_y_aermod(c) for c in cases],
    }
    rows = ["| Group | n | " + " | ".join(preds) + " |", "|---|---|" + "---|" * len(preds)]
    keyed = [(c.x if by == "x" else c.group) for c in cases]
    groups: list[tuple[str, list[int]]] = [("All", list(range(len(cases))))]
    for k in sorted(set(keyed)):
        label = f"{k:g} m" if by == "x" else f"{by} {k}"
        groups.append((label, [i for i, v in enumerate(keyed) if v == k]))
    for label, idx in groups:
        cells = []
        for p in preds.values():
            gm, f2 = score([p[i] for i in idx], [cases[i].sigma_y for i in idx])
            cells.append(f"{gm:.2f} / {f2:.0%}")
        rows.append(f"| {label} | {len(idx)} | " + " | ".join(cells) + " |")
    return rows


def main() -> None:
    """Print the tables: geometric mean of predicted / measured, then share within 2x."""
    pg, sb = load_prairie_grass(), load_sagebrush()
    stable = [c for c in pg if c.obukhov > 0]
    unstable = [c for c in pg if c.obukhov < 0]
    print(f"Prairie Grass: {len(pg)} values ({len(unstable)} unstable, {len(stable)} stable)\n")
    print("\n".join(table(pg, "x")))
    print("\nPrairie Grass by stability\n")
    print("\n".join(table(unstable, "x")[:3]).replace("| All |", "| Unstable |"))
    print("\n".join(table(stable, "x")[2:3]).replace("| All |", "| Stable |"))
    print(f"\nSagebrush Phase 1: {len(sb)} values\n")
    print("\n".join(table(sb, "x")))
    print("\nSagebrush by test (IOP)\n")
    print("\n".join(table(sb, "IOP")))


if __name__ == "__main__":
    main()
