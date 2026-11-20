"""Single-particle physics: diameter, slip correction and settling velocity.

Stokes (1851) settling with the Cunningham (1910) slip correction, then the Schiller and
Naumann (1933) drag law beyond the Stokes regime.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from .constants import MFP_AIR, MU_AIR, RHO_AIR, G

if TYPE_CHECKING:
    from .types import FloatArray


# Cunningham slip correction, Cc = 1 + Kn (A1 + A2 exp(-A3 / Kn)) with Kn = 2 lambda / d:
# the empirical coefficients as given in Seinfeld and Pandis (2016).
CUNNINGHAM_A1 = 1.257


CUNNINGHAM_A2 = 0.4


CUNNINGHAM_A3 = 1.1


# Settling regimes: Stokes (1851) drag holds for particle Reynolds numbers below about 0.1;
# above it, the Schiller and Naumann (1933) drag law, Cd = 24/Re (1 + 0.15 Re^0.687), up to
# Re = 1000, then Newton's constant Cd = 0.44.
STOKES_RE_MAX = 0.1


SCHILLER_NAUMANN_A = 0.15


SCHILLER_NAUMANN_B = 0.687


NEWTON_RE_MIN = 1000.0


NEWTON_DRAG = 0.44


def cunningham_slip(d_p: float) -> float:
    """Cunningham slip correction factor for a particle of diameter ``d_p`` (m).

    ``Cc = 1 + Kn (1.257 + 0.4 exp(-1.1 / Kn))`` with Knudsen number ``Kn = 2 lambda / d_p``.

    References
    ----------
    Cunningham (1910); coefficients as given in Seinfeld and Pandis (2016).
    """
    kn = 2.0 * MFP_AIR / d_p
    return 1.0 + kn * (CUNNINGHAM_A1 + CUNNINGHAM_A2 * math.exp(-CUNNINGHAM_A3 / kn))


def _cunningham_slip_array(d_p: FloatArray) -> FloatArray:
    """Array form of :func:`cunningham_slip` (numpy's exp, kept separate on purpose).

    numpy's and the C library's ``exp`` can differ in the last bit, so the scalar and
    array forms are not interchangeable if results must reproduce exactly.
    """
    kn = 2.0 * MFP_AIR / d_p
    out: FloatArray = 1.0 + kn * (CUNNINGHAM_A1 + CUNNINGHAM_A2 * np.exp(-CUNNINGHAM_A3 / kn))
    return out


def _drag_coefficient(re_: float) -> float:
    """Sphere drag: Schiller and Naumann (1933) below Re = 1000, Newton's 0.44 above."""
    if re_ < NEWTON_RE_MIN:
        drag: float = 24.0 / re_ * (1 + SCHILLER_NAUMANN_A * re_**SCHILLER_NAUMANN_B)
        return drag
    return NEWTON_DRAG


def particle_properties(mass_kg: float, density: float) -> tuple[float, float, float]:
    """Equivalent-sphere diameter and terminal settling velocity of one particle.

    Stokes (1851) settling with the Cunningham (1910) slip correction,
    ``v = rho g d^2 Cc / (18 mu)``. Beyond the Stokes regime (Re > 0.1) the velocity
    is found by iterating the force balance with the Schiller and Naumann (1933)
    drag law.

    Parameters
    ----------
    mass_kg
        Mass of one particle, kg.
    density
        Particle density, kg/m3.

    Returns
    -------
    tuple
        Diameter (m), settling velocity (m/s) and particle Reynolds number.

    References
    ----------
    Stokes (1851); Cunningham (1910); Schiller and Naumann (1933);
    Seinfeld and Pandis (2016).
    """
    d = (6.0 * mass_kg / (math.pi * density)) ** (1.0 / 3.0)
    cc = cunningham_slip(d)
    v = density * G * d * d * cc / (18.0 * MU_AIR)
    re_ = RHO_AIR * v * d / MU_AIR
    if re_ > STOKES_RE_MAX:
        for _ in range(200):
            re_ = max(RHO_AIR * v * d / MU_AIR, 1e-9)
            cd = _drag_coefficient(re_)
            v_new = math.sqrt(4.0 * G * d * (density - RHO_AIR) / (3.0 * cd * RHO_AIR))
            if abs(v_new - v) < 1e-9:
                break
            v = 0.5 * (v + v_new)
    return d, v, RHO_AIR * v * d / MU_AIR
