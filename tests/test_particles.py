"""Particle settling: Stokes' law with the Cunningham slip correction and inertial drag.

Reference values are from Seinfeld and Pandis (2016), Atmospheric Chemistry and
Physics, 3rd ed., ch. 9 (tables of the slip correction and of terminal settling
velocity for unit-density spheres at 298 K and 1 atm). The model uses a mean free path
of 0.068 um, slightly larger than the 0.0651 um behind those tables, which raises the
slip correction of 0.1 um particles by a few percent; tolerances allow for that.
"""

import math

import pytest

from dispersal.constants import MU_AIR, RHO_AIR, G
from dispersal.particles import (
    NEWTON_DRAG,
    NEWTON_RE_MIN,
    STOKES_RE_MAX,
    _drag_coefficient,
    cunningham_slip,
    particle_properties,
)


def sphere_mass(d_m: float, rho: float = 1000.0) -> float:
    return rho * math.pi * d_m**3 / 6.0


@pytest.mark.parametrize(
    ("d_um", "published", "tol"),
    [(0.1, 2.85, 0.05), (1.0, 1.164, 0.01), (10.0, 1.016, 0.002)],
)
def test_cunningham_slip_correction(d_um: float, published: float, tol: float) -> None:
    assert cunningham_slip(d_um * 1e-6) == pytest.approx(published, rel=tol)


def test_slip_correction_vanishes_for_large_particles() -> None:
    assert cunningham_slip(100e-6) == pytest.approx(1.0, abs=2e-3)


@pytest.mark.parametrize(
    ("d_um", "published_cm_s"),
    [(1.0, 3.5e-3), (10.0, 0.306)],
)
def test_settling_velocity_unit_density(d_um: float, published_cm_s: float) -> None:
    d, v, _ = particle_properties(sphere_mass(d_um * 1e-6), 1000.0)
    assert d == pytest.approx(d_um * 1e-6, rel=1e-12)
    assert v * 100 == pytest.approx(published_cm_s, rel=0.03)


def test_stokes_law_in_its_regime() -> None:
    """Below Re = 0.1 the velocity is exactly rho g d^2 Cc / (18 mu)."""
    d = 3e-6
    _, v, re_ = particle_properties(sphere_mass(d, 2650.0), 2650.0)
    assert re_ < STOKES_RE_MAX
    stokes = 2650.0 * G * d**2 * cunningham_slip(d) / (18 * MU_AIR)
    assert v == pytest.approx(stokes, rel=1e-12)


def test_large_particles_fall_slower_than_stokes_predicts() -> None:
    """Inertial (Schiller-Naumann) drag slows particles beyond the Stokes regime."""
    d = 100e-6
    _, v, re_ = particle_properties(sphere_mass(d), 1000.0)
    stokes = 1000.0 * G * d**2 / (18 * MU_AIR)
    assert re_ > STOKES_RE_MAX
    assert 0.6 * stokes < v < stokes
    # force balance holds at the solution: weight = drag
    cd = _drag_coefficient(re_)
    weight = (1000.0 - RHO_AIR) * G * math.pi * d**3 / 6
    drag = 0.5 * RHO_AIR * v**2 * cd * math.pi * d**2 / 4
    assert drag == pytest.approx(weight, rel=1e-6)


def test_drag_law_continuity() -> None:
    """Schiller-Naumann meets Newton's constant drag near Re = 1000 within 5%."""
    below = _drag_coefficient(NEWTON_RE_MIN * 0.999)
    assert below == pytest.approx(NEWTON_DRAG, rel=0.05)


def test_settling_increases_with_size() -> None:
    velocities = [
        particle_properties(sphere_mass(d * 1e-6), 1000.0)[1]
        for d in (0.03, 0.1, 0.3, 1, 3, 10, 30, 100, 300)
    ]
    assert velocities == sorted(velocities)


def test_lead_oxide_settles_faster_than_unit_density() -> None:
    d = 1e-6
    v_unit = particle_properties(sphere_mass(d), 1000.0)[1]
    v_pbo = particle_properties(sphere_mass(d, 9500.0), 9500.0)[1]
    assert v_pbo / v_unit == pytest.approx(9.5, rel=1e-9)  # Stokes: v proportional to rho
