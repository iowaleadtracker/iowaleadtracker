"""Removal at the ground and by water drops.

Size-resolved dry deposition after Zhang et al. (2001); drop collection efficiency after
Slinn (1984), as given in Seinfeld and Pandis (2016).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from .constants import K_BOLTZ, MU_AIR, MU_WATER, RHO_AIR, RHO_WATER, T_REF, VON_KARMAN, G
from .particles import _cunningham_slip_array, cunningham_slip, particle_properties

if TYPE_CHECKING:
    from .types import FloatArray


# Zhang et al. (2001) dry-deposition parameters by land use: roughness length z0 (m),
# collector radius A (m; None = smooth surface), alpha, gamma. From the paper's Table 3
# (p. 553), seasonal category 3, "late autumn after frost, no snow" (its Table 2), for a
# late-November blast; checked against the paper on Nov. 23, 2026. Land-use categories:
# grass 6, crops 7 ("crops, mixed farming"), forest 5 ("mixed broadleaf and needleleaf
# trees"), urban 15, desert 8, water 13/14. For water the paper gives z0 as a function of
# wind speed; a fixed calm-sea value stands in.
LAND_USE: dict[str, tuple[float, float | None, float, float]] = {
    "grass": (0.05, 5e-3, 1.2, 0.54),
    "crops": (0.02, 5e-3, 1.2, 0.54),
    "forest": (1.15, 5e-3, 0.8, 0.56),
    "urban": (1.0, 10e-3, 1.5, 0.56),
    "desert": (0.04, None, 50.0, 0.54),
    "water": (0.0002, None, 100.0, 0.50),
}

# Emerson et al. (2020), SI Appendix Table S1, "Revised": the same resistance framework and
# land-use table as Zhang et al. (2001), with six collection-efficiency coefficients refit
# to size-resolved flux measurements over forest, grassland and water. Brownian
# C_B Sc^-gamma; interception C_In (d/A)^nu; impaction C_Im (St/(alpha + St))^beta. It
# moves the deposition minimum from about 1-2 um down to about 0.05 um: the smallest particles
# deposit more slowly than with Zhang, and particles from about 0.5-1 um up faster.
EMERSON_C_B = 0.2
EMERSON_GAMMA = 2.0 / 3.0
EMERSON_C_IN = 2.5
EMERSON_NU = 0.8
EMERSON_C_IM = 0.4
EMERSON_BETA = 1.7
#: Dry-deposition schemes: the first is the default, the second its observational revision.
DEPOSITION_SCHEMES = ("zhang", "emerson")
DEPOSITION_CITES = {"zhang": "Zhang et al. (2001)", "emerson": "Emerson et al. (2020)"}


def zhang_surface_terms(d_p: FloatArray, rho_p: FloatArray | float, T: float = T_REF) -> FloatArray:
    """Schmidt number of each particle, the per-particle constant of the Zhang scheme.

    ``Sc = nu / D_B`` with the Stokes-Einstein Brownian diffusivity
    ``D_B = k T Cc / (3 pi mu d_p)``. ``rho_p`` is accepted for a uniform signature.

    References
    ----------
    Zhang, Gong, Padro and Barrie (2001); Seinfeld and Pandis (2016).
    """
    del rho_p  # the Schmidt number does not depend on density
    cc = _cunningham_slip_array(d_p)
    diff = K_BOLTZ * T * cc / (3.0 * math.pi * MU_AIR * d_p)
    out: FloatArray = (MU_AIR / RHO_AIR) / diff
    return out


def zhang_deposition_velocity(
    d_p: FloatArray,
    v_g: FloatArray,
    schmidt: FloatArray,
    u10: FloatArray,
    land_use: str,
    scheme: str = "zhang",
) -> FloatArray:
    """Size-resolved dry deposition velocity (m/s).

    ``v_d = v_g + 1 / (R_a + R_s)``: gravitational settling plus transfer through a
    neutral-stability aerodynamic resistance from the 10 m wind and a surface
    resistance from Brownian diffusion, impaction and interception. Arrays broadcast
    together.

    Parameters
    ----------
    d_p, v_g, schmidt
        Particle diameter (m), settling velocity (m/s) and Schmidt number.
    u10
        10 m wind speed, m/s (floored at 0.5).
    land_use
        Key of :data:`LAND_USE` (roughness length and collector parameters).
    scheme
        ``"zhang"`` (Zhang et al. 2001) or ``"emerson"`` (the revised collection
        efficiencies of Emerson et al. 2020, SI Table S1).

    References
    ----------
    Zhang, Gong, Padro and Barrie (2001); Emerson et al. (2020).
    """
    z0, A, alpha, gamma = LAND_USE[land_use]
    if scheme not in DEPOSITION_SCHEMES:
        raise ValueError(f"unknown deposition scheme {scheme!r}")
    emerson = scheme == "emerson"
    ustar = np.maximum(VON_KARMAN * np.maximum(u10, 0.5) / math.log(10.0 / z0), 0.01)
    r_a = math.log(10.0 / z0) / (VON_KARMAN * ustar)
    e_b = EMERSON_C_B * schmidt ** (-EMERSON_GAMMA) if emerson else schmidt ** (-gamma)
    if A is None:  # smooth surface
        st = v_g * ustar**2 / (G * MU_AIR / RHO_AIR)
        e_in: FloatArray | float = 0.0
    else:
        st = v_g * ustar / (G * A)
        e_in = EMERSON_C_IN * (d_p / A) ** EMERSON_NU if emerson else 0.5 * (d_p / A) ** 2
    if emerson:
        e_im = EMERSON_C_IM * (st / (alpha + st)) ** EMERSON_BETA
    else:
        e_im = (st / (alpha + st)) ** 2
    r1 = np.exp(-np.sqrt(st))  # fraction that sticks
    r_s = 1.0 / (3.0 * ustar * np.maximum((e_b + e_im + e_in) * r1, 1e-12))
    out: FloatArray = v_g + 1.0 / (r_a + r_s)
    return out


def slinn_efficiency(d_p: float, rho_p: float, drop_d: float, T: float = T_REF) -> float:
    """Return the collection efficiency of a falling water drop for an aerosol particle.

    The sum of Brownian diffusion, interception and inertial impaction terms
    (impaction only above the critical Stokes number), capped at 1.

    Parameters
    ----------
    d_p, rho_p
        Particle diameter (m) and density (kg/m3).
    drop_d
        Drop diameter, m.
    T
        Air temperature, K.

    References
    ----------
    Slinn (1984), as given in Seinfeld and Pandis (2016).
    """
    _, u_t, _ = particle_properties(RHO_WATER * math.pi * drop_d**3 / 6.0, RHO_WATER)  # drop
    _, v_p, _ = particle_properties(rho_p * math.pi * d_p**3 / 6.0, rho_p)
    cc = cunningham_slip(d_p)
    diff = K_BOLTZ * T * cc / (3.0 * math.pi * MU_AIR * d_p)
    re_ = drop_d * u_t * RHO_AIR / (2.0 * MU_AIR)
    sc = MU_AIR / (RHO_AIR * diff)
    phi = d_p / drop_d
    omega = MU_WATER / MU_AIR
    tau = rho_p * d_p**2 * cc / (18.0 * MU_AIR)
    st = 2.0 * tau * (u_t - v_p) / drop_d
    s_star = (1.2 + math.log(1 + re_) / 12.0) / (1.0 + math.log(1 + re_))
    e = 4.0 / (re_ * sc) * (
        1 + 0.4 * re_**0.5 * sc ** (1 / 3) + 0.16 * re_**0.5 * sc**0.5
    ) + 4.0 * phi * (1.0 / omega + (1 + 2 * re_**0.5) * phi)
    if st > s_star:
        e += ((st - s_star) / (st - s_star + 2.0 / 3.0)) ** 1.5
    efficiency: float = min(e, 1.0)
    return efficiency


def spray_coefficient(d_p: float, rho_p: float, flux_m_s: float, drop_d: float) -> float:
    """Below-drop scavenging coefficient (1/s) for a water spray: ``3 J E / (2 D)``.

    ``J`` is the water flux (m/s), ``E`` the Slinn collection efficiency and ``D`` the
    drop diameter (m).

    References
    ----------
    Seinfeld and Pandis (2016), below-cloud scavenging of particles.
    """
    return 1.5 * flux_m_s * slinn_efficiency(d_p, rho_p, drop_d) / drop_d
