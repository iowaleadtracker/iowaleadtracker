"""Dry deposition (Zhang et al. 2001) and drop scavenging (Slinn 1984).

These check the qualitative behavior of the schemes, not tabulated numbers:
deposition velocity is lowest around 1 um, where neither Brownian diffusion (small
particles) nor settling and impaction (large ones) is efficient, never falls below
gravitational settling, and rises with wind speed; drop collection efficiency has the
"Greenfield gap" minimum between diffusion-dominated small particles and
impaction-dominated large ones. See Seinfeld and Pandis (2016).
"""

import math

import numpy as np
import pytest

from dispersal.deposition import (
    LAND_USE,
    deposition_velocity,
    schmidt_number,
    slinn_efficiency,
    spray_coefficient,
)
from dispersal.particles import particle_properties

SIZES_UM = np.array([0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0])


def deposition(
    sizes_um: np.ndarray, u10: float, land_use: str = "grass"
) -> tuple[np.ndarray, np.ndarray]:
    d = sizes_um * 1e-6
    rho = 1000.0
    vg = np.array([particle_properties(rho * math.pi * x**3 / 6, rho)[1] for x in d])
    sc = schmidt_number(d, rho)
    return deposition_velocity(d, vg, sc, np.full_like(d, u10), land_use), vg


def test_deposition_never_below_settling() -> None:
    for land_use in LAND_USE:
        vd, vg = deposition(SIZES_UM, 5.0, land_use)
        assert np.all(vd >= vg), land_use


def test_deposition_minimum_near_one_micrometre() -> None:
    fine = np.array([0.01, 0.03, 0.1, 0.3, 0.5, 1.0, 2.0, 3.0, 10.0, 30.0])
    vd, _ = deposition(fine, 5.0)
    low = int(np.argmin(vd))
    assert 0.3 <= fine[low] <= 3.0
    assert vd[0] > 5 * vd[low]  # diffusion takes over below
    assert vd[-1] > 5 * vd[low]  # settling and impaction take over above


def test_deposition_rises_with_wind() -> None:
    calm, _ = deposition(SIZES_UM, 2.0)
    windy, _ = deposition(SIZES_UM, 10.0)
    assert np.all(windy >= calm)
    assert windy[SIZES_UM == 1.0][0] > calm[SIZES_UM == 1.0][0]


def test_settling_is_the_largest_term_for_coarse_particles() -> None:
    """At 30 um, settling outweighs everything the surface resistance adds."""
    vd, vg = deposition(np.array([30.0]), 5.0)
    assert vg[0] > vd[0] - vg[0] > 0


def test_schmidt_number_grows_with_size() -> None:
    """Brownian diffusivity falls with size, so Sc = nu / D rises."""
    sc = schmidt_number(SIZES_UM * 1e-6, 1000.0)
    assert np.all(np.diff(sc) > 0)


def test_slinn_efficiency_bounds_and_greenfield_gap() -> None:
    drop = 1e-3  # 1 mm drop
    eff = {d: slinn_efficiency(d * 1e-6, 1000.0, drop) for d in SIZES_UM}
    assert all(0.0 < e <= 1.0 for e in eff.values())
    gap = min(eff, key=lambda d: eff[d])
    assert 0.1 <= gap <= 3.0
    assert eff[0.01] > eff[gap]  # diffusion wins for the smallest
    assert eff[30.0] > eff[gap]  # impaction wins for the largest


def test_spray_coefficient_formula() -> None:
    """Below-drop scavenging coefficient = 3 J E / (2 D)."""
    d_p, rho, flux, drop = 1e-6, 9500.0, 2e-4, 1e-3
    expected = 1.5 * flux * slinn_efficiency(d_p, rho, drop) / drop
    assert spray_coefficient(d_p, rho, flux, drop) == pytest.approx(expected, rel=1e-15)


def test_land_use_constants_match_zhang_table_3_late_autumn() -> None:
    """Zhang et al. (2001) Table 3, seasonal category 3 (late autumn after frost, no snow)."""
    assert LAND_USE["grass"] == (0.05, 5e-3, 1.2, 0.54)  # LUC 6
    assert LAND_USE["crops"] == (0.02, 5e-3, 1.2, 0.54)  # LUC 7, crops and mixed farming
    assert LAND_USE["forest"] == (1.15, 5e-3, 0.8, 0.56)  # LUC 5, mixed forest
    assert LAND_USE["urban"] == (1.0, 10e-3, 1.5, 0.56)  # LUC 15
    assert LAND_USE["desert"] == (0.04, None, 50.0, 0.54)  # LUC 8
    assert LAND_USE["water"][1:] == (None, 100.0, 0.50)  # LUC 13/14 (z0 a function of wind)


def test_emerson_coefficients_match_table_s1() -> None:
    """Emerson et al. (2020), SI Appendix Table S1, "Revised" column."""
    from dispersal import deposition as dep  # noqa: PLC0415

    assert (dep.EMERSON_C_B, dep.EMERSON_GAMMA) == (0.2, 2.0 / 3.0)
    assert (dep.EMERSON_C_IN, dep.EMERSON_NU) == (2.5, 0.8)
    assert (dep.EMERSON_C_IM, dep.EMERSON_BETA) == (0.4, 1.7)
    assert dep.DEPOSITION_SCHEMES == ("zhang", "emerson")


def test_zhang_is_the_default_and_unchanged() -> None:
    d = SIZES_UM * 1e-6
    vg = np.array([particle_properties(1000.0 * math.pi * x**3 / 6, 1000.0)[1] for x in d])
    sc = schmidt_number(d, 1000.0)
    u = np.full_like(d, 5.0)
    default = deposition_velocity(d, vg, sc, u, "crops")
    assert np.array_equal(default, deposition_velocity(d, vg, sc, u, "crops", "zhang"))


def test_emerson_matches_its_figure_2b() -> None:
    """Emerson et al. (2020) Fig. 2B (needleleaf forest, u* = 0.4 m/s, 1,500 kg/m3).

    Minimum near 0.05 um at about 0.1-0.2 cm/s; about 0.6 cm/s at 1 um and about 3 cm/s
    at 10 um. Zhang's minimum (Fig. 2A) is near 1-2 um.
    """
    from dispersal import deposition as dep  # noqa: PLC0415

    rho = 1500.0
    sizes = np.array([0.01, 0.03, 0.05, 0.1, 0.3, 1.0, 2.0, 3.0, 10.0])
    d = sizes * 1e-6
    vg = np.array([particle_properties(rho * math.pi * x**3 / 6, rho)[1] for x in d])
    sc = schmidt_number(d, rho)
    dep.LAND_USE["_needleleaf"] = (1.15, 2e-3, 1.0, 0.56)  # LUC 1 alpha and A (Table 3)
    try:
        u10 = np.full_like(d, 0.4 * math.log(10 / 1.15) / 0.41)  # u* = 0.4 m/s
        em = deposition_velocity(d, vg, sc, u10, "_needleleaf", "emerson") * 100
        zh = deposition_velocity(d, vg, sc, u10, "_needleleaf", "zhang") * 100
    finally:
        del dep.LAND_USE["_needleleaf"]
    assert sizes[np.argmin(em)] in (0.03, 0.05, 0.1)
    assert sizes[np.argmin(zh)] in (1.0, 2.0)
    assert 0.08 < float(np.min(em)) < 0.25
    assert 0.4 < em[sizes == 1.0][0] < 0.9
    assert 2.0 < em[sizes == 10.0][0] < 4.5
    assert em[sizes == 0.01][0] < zh[sizes == 0.01][0]  # less Brownian loss
    assert em[sizes == 1.0][0] > 3 * zh[sizes == 1.0][0]  # more interception


def test_unknown_scheme_is_refused() -> None:
    d = np.array([1e-6])
    with pytest.raises(ValueError, match="unknown deposition scheme"):
        deposition_velocity(d, d, d, d, "grass", "other")
