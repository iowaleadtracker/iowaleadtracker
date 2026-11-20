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
    slinn_efficiency,
    spray_coefficient,
    zhang_deposition_velocity,
    zhang_surface_terms,
)
from dispersal.particles import particle_properties

SIZES_UM = np.array([0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0])


def deposition(
    sizes_um: np.ndarray, u10: float, land_use: str = "grass"
) -> tuple[np.ndarray, np.ndarray]:
    d = sizes_um * 1e-6
    rho = 1000.0
    vg = np.array([particle_properties(rho * math.pi * x**3 / 6, rho)[1] for x in d])
    sc = zhang_surface_terms(d, rho)
    return zhang_deposition_velocity(d, vg, sc, np.full_like(d, u10), land_use), vg


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
    sc = zhang_surface_terms(SIZES_UM * 1e-6, 1000.0)
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
