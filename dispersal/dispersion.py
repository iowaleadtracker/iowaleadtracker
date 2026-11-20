"""Atmospheric dispersion: stability, puff growth and ground reflection.

Pasquill (1961) stability classes as tabulated by Turner (1970), Briggs (1973) rural
sigma curves with virtual-distance growth, ground and mixing-lid reflection, and the
error function used to integrate Gaussians.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .types import ArrayOrFloat, FloatArray, IntArray


# Briggs (1973) rural dispersion curves, sigma = c * x * (1 + k x)^e (x in m), for
# Pasquill classes A-F, as tabulated in Seinfeld and Pandis (2016).
SY_C = np.array([0.22, 0.16, 0.11, 0.08, 0.06, 0.04])


SY_K = np.full(6, 1e-4)


SY_E = np.full(6, -0.5)


SZ_C = np.array([0.20, 0.12, 0.08, 0.06, 0.03, 0.016])


SZ_K = np.array([0.0, 0.0, 2e-4, 1.5e-3, 3e-4, 3e-4])


SZ_E = np.array([0.0, 0.0, -0.5, -0.5, -1.0, -1.0])


# Wind-profile power-law exponents (rural) and fallback mixing heights by class.
PROFILE_P = np.array([0.07, 0.07, 0.10, 0.15, 0.35, 0.55])


DEFAULT_BLH = np.array([1500.0, 1200.0, 1000.0, 800.0, 400.0, 200.0])


# Once sigma_z exceeds 1.6 times the mixing height, the puff is taken as uniformly mixed
# between the ground and the lid (a standard screening-model criterion).
WELL_MIXED_SIGMA_Z = 1.6


# Pasquill (1961) stability classes as tabulated by Turner (1970). Rows: 10 m wind bands
# split at WIND_BANDS (m/s). Day columns: strong, moderate, slight insolation. Night
# columns: cloudy (>= 50 %), clear. Turner's half classes (A-B, B-C, C-D) are resolved here
# to the more unstable class. Overcast skies (>= 90 %) are neutral (D) day and night.
WIND_BANDS = [2.0, 3.0, 5.0, 6.0]


DAY_TABLE = np.array([[0, 0, 1], [0, 1, 2], [1, 1, 2], [2, 2, 3], [2, 3, 3]])


NIGHT_TABLE = np.array([[4, 5], [4, 5], [3, 4], [3, 3], [3, 3]])


DAYTIME_SW = 10.0  # W/m2: sun up


STRONG_SW = 600  # W/m2 of shortwave radiation for "strong" insolation


MODERATE_SW = 300


NIGHT_CLOUDY = 50  # % cloud cover


OVERCAST = 90


def stability_class(u: ArrayOrFloat, sw: ArrayOrFloat, cloud: ArrayOrFloat) -> IntArray:
    """Pasquill stability class index 0..5 (A..F) from wind, sunshine and cloud.

    The screening method of Pasquill (1961) as tabulated by Turner (1970), with
    incoming shortwave radiation standing in for insolation: :data:`DAY_TABLE` by day,
    :data:`NIGHT_TABLE` by night, and neutral (D) under overcast skies.

    Parameters
    ----------
    u
        10 m wind speed, m/s.
    sw
        Incoming shortwave radiation, W/m2 (above 10 counts as day).
    cloud
        Total cloud cover, %.

    References
    ----------
    Pasquill (1961); Turner (1970).
    """
    u = np.asarray(u, float)
    sw = np.asarray(sw)
    cloud = np.asarray(cloud)
    day = sw > DAYTIME_SW
    ins = np.where(sw > STRONG_SW, 0, np.where(sw > MODERATE_SW, 1, 2))
    ub = np.digitize(u, WIND_BANDS)  # 0..4
    cls = np.where(day, DAY_TABLE[ub, ins], NIGHT_TABLE[ub, (cloud < NIGHT_CLOUDY).astype(int)])
    out: IntArray = np.where(cloud >= OVERCAST, 3, cls)
    return out


def briggs(c: ArrayOrFloat, k: ArrayOrFloat, e: ArrayOrFloat, x: ArrayOrFloat) -> FloatArray:
    """Briggs (1973) dispersion curve ``sigma = c x (1 + k x)^e`` at downwind distance x (m).

    References
    ----------
    Briggs (1973); Seinfeld and Pandis (2016).
    """
    out: FloatArray = c * x * (1.0 + k * x) ** e
    return out


def grow_sigma(
    sig: FloatArray,
    cls: IntArray,
    ds: FloatArray,
    C: FloatArray,
    K: FloatArray,
    E: FloatArray,
) -> FloatArray:
    """Advance puff sizes by travel distance ``ds`` with the virtual-distance method.

    Each puff's current sigma is matched to the distance at which the Briggs curve for
    its present stability class gives that sigma (bisection on log10 x); the puff
    then grows along that curve. Sigma never shrinks when the class changes.
    """
    c, k, e = C[cls], K[cls], E[cls]
    lo = np.full_like(sig, -3.0)
    hi = np.full_like(sig, 8.0)
    for _ in range(45):  # bisection on log10(x)
        mid = 0.5 * (lo + hi)
        below = briggs(c, k, e, 10.0**mid) < sig
        lo = np.where(below, mid, lo)
        hi = np.where(below, hi, mid)
    xv = 10.0**hi
    out: FloatArray = np.maximum(sig, briggs(c, k, e, xv + ds))
    return out


def ground_factor(h: FloatArray, sz: FloatArray, lid: FloatArray) -> FloatArray:
    """Vertical Gaussian density at the ground (1/m) for puffs at height ``h``.

    Includes the ground reflection and, under a finite mixing lid, the first image
    pairs reflected between ground and lid. Once ``sz > 1.6 * lid`` the puff is taken
    as uniformly mixed, ``1 / lid``.

    References
    ----------
    Turner (1970); Seinfeld and Pandis (2016).
    """
    out = np.zeros_like(sz)
    for n in range(-2, 3):
        if n == 0:
            out += np.exp(-0.5 * (h / sz) ** 2)
        else:
            out += np.where(np.isfinite(lid), np.exp(-0.5 * ((h + 2 * n * lid) / sz) ** 2), 0.0)
    g = 2.0 * out / (math.sqrt(2 * math.pi) * sz)
    mixed = np.isfinite(lid) & (sz > WELL_MIXED_SIGMA_Z * lid)
    result: FloatArray = np.where(mixed, 1.0 / np.where(np.isfinite(lid), lid, 1.0), g)
    return result


def _erf_approx(v: FloatArray) -> FloatArray:
    """Error function to about 1.5e-7, Abramowitz and Stegun (1964) formula 7.1.26."""
    s = np.sign(v)
    v = np.abs(v)
    t = 1.0 / (1.0 + 0.3275911 * v)
    p = t * (
        0.254829592 + t * (-0.284496736 + t * (1.421413741 + t * (-1.453152027 + t * 1.061405429)))
    )
    out: FloatArray = s * (1.0 - p * np.exp(-v * v))
    return out


try:
    from scipy.special import erf as _scipy_erf
except ImportError:  # scipy is optional
    _scipy_erf = None


def erf(v: FloatArray) -> FloatArray:
    """Error function: scipy's when installed, else :func:`_erf_approx`."""
    if _scipy_erf is not None:
        exact: FloatArray = _scipy_erf(v)
        return exact
    return _erf_approx(v)
