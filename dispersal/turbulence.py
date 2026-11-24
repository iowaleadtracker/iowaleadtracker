"""Turbulence-based puff growth (``--spread turbulence``).

The alternative to the Briggs stability-class curves in :mod:`dispersion`. Each time
step, each puff grows at a rate set by the turbulence at its height:

1. friction velocity u*, Obukhov length L and convective velocity w* from the 10 m
   wind, shortwave radiation, cloud cover, air temperature and mixing height, by the
   methods of AERMOD's meteorological preprocessor (EPA 2026, Sec. 3);
2. the crosswind and vertical turbulence sigma_v and sigma_w from CALPUFF's similarity
   formulas (Scire et al. 2000, Eqs. 2-52 to 2-64), with minimum values;
3. puff growth sigma_y = sigma_v t f_y(t) and sigma_z = sigma_w t f_z(t) with Draxler's
   (1976) travel-time functions (Scire et al. 2000, Eqs. 2-65 to 2-67), advanced from
   each puff's current size by the virtual-time method; once sigma_y passes 550 m it
   grows linearly at sigma_v, the long-range switch CALPUFF makes to Heffter's (1965)
   linear growth (Scire et al. 2000, p. 2-29), here at the turbulence rate.

sigma_v is a 1-hour value. ``averaging`` scales it for the crosswind growth by
(averaging / 60 min)^0.2, CALPUFF's averaging-time rule (Scire et al. 2000, Eq. 2-72);
the default 10 min matches the 10-minute tracer samples the scheme is checked against
and gives a narrower, more concentrated cloud. See TURBULENCE.md.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from .constants import VON_KARMAN, G

if TYPE_CHECKING:
    from collections.abc import Callable

    from .types import ArrayOrFloat, BoolArray, FloatArray, IntArray

# Energy balance (EPA 2026, AERMOD Model Formulation, Eqs. 2-3; Holtslag and van Ulden).
C1_RN = 5.31e-13  # W m-2 K-6, clear-sky incoming longwave coefficient
C2_RN = 60.0  # W m-2, cloud term
C3_RN = 0.12  # soil heat flux / net radiation coefficient
SIGMA_SB = 5.67e-8  # W m-2 K-4, Stefan-Boltzmann constant
RHO_CP = 1.2 * 1004.0  # J m-3 K-1, air density times specific heat
H_FRACTION = 0.9  # H = 0.9 Rn / (1 + 1/Bo): ground heat flux G = 0.1 Rn (EPA 2026, Eq. 2)
ALBEDO = 0.2  # assumed, midday value for harvested cropland
BOWEN = 1.0  # assumed Bowen ratio for moist late-autumn fields (sensitivity in TURBULENCE.md)
T_AIR_DEFAULT = 288.15  # K, ICAO standard atmosphere; used when no temperature is available
Z_REF = 10.0  # m, height of the reference wind
BETA_M = 5.0  # stable-profile coefficient (EPA 2026, Eq. 12)
THETA_STAR_0 = 0.09  # K, theta* = 0.09 (1 - 0.5 n^2) (EPA 2026, Eq. 16)
MAX_HEAT_LOSS = 0.05  # m s-1 K, cap on theta* u* (EPA 2026, Eq. 21)
L_NEUTRAL = -1e5  # m, start of the Monin-Obukhov iteration
N_ITER = 8  # Monin-Obukhov iterations (converged well below 1% for these inputs)

# Turbulence minimums. sigma_w by stability class A-F as CALPUFF's SWMIN defaults
# (Scire et al. 2000, Input Group 12); sigma_v as AERMOD's (EPA 2026, Eq. 115).
SIGMA_V_MIN_DEFAULT = 0.2  # m/s
SIGMA_W_MIN = np.array([0.20, 0.12, 0.08, 0.06, 0.03, 0.016])  # m/s

# Draxler (1976) time scales (s) and the Heffter switch (Scire et al. 2000, Eqs. 2-65 to
# 2-67; SYTDEP default 550 m).
TY_DAY = 1000.0
TZ_UNSTABLE = 500.0
TZ_STABLE = 100.0
SYTDEP = 550.0  # m
AVERAGING_BASE_MIN = 60.0  # sigma_v is a 1-hour value
AVERAGING_EXPONENT = 0.2  # Scire et al. 2000, Eq. 2-72
AVERAGING_DEFAULT_MIN = 10.0

SPREAD_METHODS = ("briggs", "turbulence")
"""``--spread`` choices: the Briggs stability-class curves (original) or this module."""

WEATHER_VARS = ("temperature_2m",)
"""Extra hourly Open-Meteo variables this scheme uses (2 m air temperature)."""


def spread_weather(a: object) -> tuple[str, ...]:
    """Extra weather variables to request for the run's ``--spread`` method.

    None for Briggs, or when ``--air-temperature-c`` fixes the temperature.
    """
    if getattr(a, "spread", "briggs") != "turbulence":
        return ()
    return () if getattr(a, "air_temperature_c", None) is not None else WEATHER_VARS


def _psi_m(zeta: FloatArray) -> FloatArray:
    """Unstable momentum stability function (Businger-Dyer form used by AERMET).

    References
    ----------
    EPA (2026), AERMOD Model Formulation, Eq. 7.
    """
    mu = (1.0 - 16.0 * zeta) ** 0.25
    out: FloatArray = (
        2 * np.log((1 + mu) / 2) + np.log((1 + mu**2) / 2) - 2 * np.arctan(mu) + math.pi / 2
    )
    return out


def scaling(
    u10: ArrayOrFloat,
    sw: ArrayOrFloat,
    cloud: ArrayOrFloat,
    mixing_height: ArrayOrFloat,
    z0: float,
    t_air: ArrayOrFloat = T_AIR_DEFAULT,
) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Friction velocity u* (m/s), Obukhov length L (m) and convective velocity w* (m/s).

    By day (positive net radiation): net radiation from measured shortwave radiation,
    cloud cover and temperature (Holtslag and van Ulden), sensible heat flux
    H = 0.9 Rn / (1 + 1/Bo), then u* and L by Monin-Obukhov iteration and
    w* = (g H z_i / (rho c_p T))^(1/3). At night: theta* = 0.09 (1 - 0.5 n^2) and the
    stable u* quadratic, both scaled down below the critical wind speed, with the heat
    loss capped.

    Parameters
    ----------
    u10
        10 m wind speed, m/s.
    sw
        Incoming shortwave radiation, W/m2.
    cloud
        Total cloud cover, %.
    mixing_height
        Mixing height, m.
    z0
        Roughness length, m.
    t_air
        Air temperature, K.

    References
    ----------
    EPA (2026), AERMOD Model Formulation, Sec. 3 (Eqs. 2-16, 21).
    """
    u = np.maximum(np.asarray(u10, float), 0.5)
    n = np.clip(np.asarray(cloud, float) / 100.0, 0.0, 1.0)
    t = np.broadcast_to(np.asarray(t_air, float), u.shape)
    sw_ = np.asarray(sw, float)
    rn = ((1 - ALBEDO) * sw_ + C1_RN * t**6 - SIGMA_SB * t**4 + C2_RN * n) / (1 + C3_RN)
    day = rn > 0
    ln_z = math.log(Z_REF / z0)
    # Convective: iterate u* and L.
    h = H_FRACTION * np.maximum(rn, 0.0) / (1 + 1 / BOWEN)
    us = VON_KARMAN * u / ln_z
    ell = np.full_like(u, L_NEUTRAL)
    for _ in range(N_ITER):
        ell = -RHO_CP * t * us**3 / (VON_KARMAN * G * np.maximum(h, 1e-3))
        zeta = np.clip(Z_REF / ell, -50.0, 0.0)
        zeta0 = np.clip(z0 / ell, -50.0, 0.0)
        us = VON_KARMAN * u / (ln_z - _psi_m(zeta) + _psi_m(zeta0))
    w_star = np.cbrt(G * np.maximum(h, 0.0) * np.asarray(mixing_height, float) / (RHO_CP * t))
    # Stable: theta* method.
    th = THETA_STAR_0 * (1 - 0.5 * n**2)
    cd = VON_KARMAN / ln_z
    u_cr = np.sqrt(4 * BETA_M * Z_REF * G * th / (t * cd))
    u_eff = np.maximum(u, u_cr)
    u0 = np.sqrt(BETA_M * Z_REF * G * th / t)
    root = np.sqrt(np.clip(1 - (2 * u0 / (math.sqrt(cd) * u_eff)) ** 2, 0.0, None))
    us_s = cd * u_eff / 2 * (1 + root)
    scale = np.where(u < u_cr, u / u_cr, 1.0)
    us_s = us_s * scale
    th = np.minimum(th * scale, MAX_HEAT_LOSS / np.maximum(us_s, 1e-3))
    ell_s = t * us_s**2 / (VON_KARMAN * G * np.maximum(th, 1e-4))
    return (
        np.where(day, us, us_s),
        np.where(day, ell, ell_s),
        np.where(day, w_star, 0.0),
    )


def sigma_vw(
    u_star: FloatArray,
    obukhov: FloatArray,
    w_star: FloatArray,
    z: FloatArray,
    mixing_height: FloatArray,
    cls: IntArray,
    sigma_v_min: float = SIGMA_V_MIN_DEFAULT,
) -> tuple[FloatArray, FloatArray]:
    """Crosswind and vertical turbulence sigma_v, sigma_w (m/s) at height ``z``.

    CALPUFF's similarity profiles: unstable side (L < 0) Eqs. 2-52 to 2-61, neutral and
    stable side Eqs. 2-62 to 2-64. Above the mixing height the turbulence falls to the
    minimums: sigma_v to ``sigma_v_min``, sigma_w to CALPUFF's value for the class.

    References
    ----------
    Scire, Strimaitis and Yamartino (2000), Eqs. 2-52 to 2-64 and Input Group 12.
    """
    z = np.maximum(np.asarray(z, float), 1.0)
    h = np.maximum(np.asarray(mixing_height, float), 20.0)
    zr = np.minimum(z / h, 1.2)
    a_n = np.exp(-0.9 * zr)
    unstable = obukhov < 0
    sv_u = np.sqrt(4 * u_star**2 * a_n**2 + 0.35 * w_star**2)
    neg_zl = np.clip(-z / np.where(unstable, obukhov, -1e9), 0.0, None)
    sw_surface = np.sqrt(1.6 * u_star**2 * a_n**2 + 2.9 * u_star**2 * neg_zl ** (2 / 3))
    sw_mixed = np.sqrt(1.15 * u_star**2 * a_n**2 + 0.35 * w_star**2)
    # Entrainment layer (0.8-1.2 h): CALPUFF tapers the convective term; half is the
    # midpoint of its a_c1 (1/2 to 1) and a_c2 (1/3 to 1) ramps.
    sw_entrain = np.sqrt(1.15 * u_star**2 * a_n**2 + 0.5 * 0.35 * w_star**2)
    sw_u = np.where(zr <= 0.1, sw_surface, np.where(zr <= 0.8, sw_mixed, sw_entrain))
    cs = np.clip(1.0 - zr, 0.0, None) ** 0.75
    zl = np.clip(z / np.where(unstable, 1e9, obukhov), 0.0, None)
    sv_s = u_star * (1.6 * cs * zl + 1.8 * a_n) / (1 + zl)
    sw_s = 1.3 * u_star * (cs * zl + a_n) / (1 + zl)
    above = z > h
    sv = np.where(above, 0.0, np.where(unstable, sv_u, sv_s))
    sw = np.where(above, 0.0, np.where(unstable, sw_u, sw_s))
    return np.maximum(sv, sigma_v_min), np.maximum(sw, SIGMA_W_MIN[np.asarray(cls, int)])


def draxler_fy(t: ArrayOrFloat) -> FloatArray:
    """Draxler's crosswind travel-time function f_y(t) = 1 / (1 + 0.9 (t/1000 s)^0.5).

    References
    ----------
    Draxler (1976), as given by Scire, Strimaitis and Yamartino (2000), Eq. 2-65.
    """
    out: FloatArray = 1.0 / (1.0 + 0.9 * np.sqrt(np.asarray(t, float) / TY_DAY))
    return out


def draxler_fz(t: ArrayOrFloat, stable: BoolArray) -> FloatArray:
    """Draxler's vertical travel-time function: unstable/neutral or stable form.

    f_z = 1 / (1 + 0.9 (t/500 s)^0.5) for L < 0 and 1 / (1 + 0.945 (t/100 s)^0.806)
    for L > 0.

    References
    ----------
    Draxler (1976), as given by Scire, Strimaitis and Yamartino (2000), Eqs. 2-66, 2-67.
    """
    t = np.asarray(t, float)
    out: FloatArray = np.where(
        stable,
        1.0 / (1.0 + 0.945 * (t / TZ_STABLE) ** 0.806),
        1.0 / (1.0 + 0.9 * np.sqrt(t / TZ_UNSTABLE)),
    )
    return out


def _virtual_time(
    sig: FloatArray, s: FloatArray, f: Callable[[FloatArray], FloatArray]
) -> FloatArray:
    """Travel time at which s t f(t) equals the puff's current sigma (bisection on log10 t)."""
    lo = np.full_like(sig, -2.0)
    hi = np.full_like(sig, 7.0)
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        t = 10.0**mid
        below = s * t * f(t) < sig
        lo = np.where(below, mid, lo)
        hi = np.where(below, hi, mid)
    out: FloatArray = 10.0**hi
    return out


def averaging_factor(averaging_min: float) -> float:
    """Crosswind scale factor (averaging / 60 min)^0.2 for a sigma_v given as a 1-hour value.

    References
    ----------
    Scire, Strimaitis and Yamartino (2000), Eq. 2-72.
    """
    return float((averaging_min / AVERAGING_BASE_MIN) ** AVERAGING_EXPONENT)


def grow(
    sy: FloatArray,
    sz: FloatArray,
    sigma_v: FloatArray,
    sigma_w: FloatArray,
    stable: BoolArray,
    dt: float | FloatArray,
    averaging_min: float = AVERAGING_DEFAULT_MIN,
) -> tuple[FloatArray, FloatArray]:
    """Advance puff sizes by one time step of ``dt`` seconds (a scalar or one per puff).

    Below 550 m, sigma_y follows sigma_v t f_y(t) from the travel time at which the
    curve gives the puff's present size; above it, sigma_y grows linearly at sigma_v.
    sigma_z follows sigma_w t f_z(t) the same way. Sizes never shrink.

    References
    ----------
    Draxler (1976); Scire, Strimaitis and Yamartino (2000), Eqs. 2-39 to 2-42, 2-65 to
    2-67, 2-72 and p. 2-29; Heffter (1965).
    """
    sv = sigma_v * averaging_factor(averaging_min)
    tv = _virtual_time(sy, sv, draxler_fy)
    sy_near = np.maximum(sy, sv * (tv + dt) * draxler_fy(tv + dt))
    sy_new: FloatArray = np.where(sy >= SYTDEP, sy + sv * dt, sy_near)

    def fz(t: FloatArray) -> FloatArray:
        return draxler_fz(t, stable)

    tz = _virtual_time(sz, sigma_w, fz)
    sz_new: FloatArray = np.maximum(sz, sigma_w * (tz + dt) * fz(tz + dt))
    return sy_new, sz_new
