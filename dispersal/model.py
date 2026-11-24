"""The Lagrangian Gaussian puff model.

Release, transport, growth, settling, the residual layer (Stull 1988), dry and wet
deposition, spray removal, and the hourly mass budget.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from .constants import R_EARTH
from .deposition import (
    LAND_USE,
    deposition_velocity,
    schmidt_number,
    slinn_efficiency,
    spray_coefficient,
)
from .dispersion import (
    SY_C,
    SY_E,
    SY_K,
    SZ_C,
    SZ_E,
    SZ_K,
    WELL_MIXED_SIGMA_Z,
    erf,
    ground_factor,
    grow_sigma,
)
from .met import MetField, transport_wind
from .turbulence import AVERAGING_DEFAULT_MIN, SIGMA_V_MIN_DEFAULT, T_AIR_DEFAULT, sigma_vw
from .turbulence import grow as turbulent_grow
from .turbulence import scaling as turbulence_scaling

if TYPE_CHECKING:
    import argparse
    from collections.abc import Sequence

    from .types import Bin, BoolArray, FloatArray, IntArray, Json, Record


def build_puffs(a: argparse.Namespace, bins: Sequence[Bin]) -> dict[str, FloatArray]:
    """Build the initial puff set: release times x cloud layers x particle-size bins.

    An explosion is one instant release spread evenly from the ground to the Church
    cloud top in ``--cloud-layers`` layers; other releases are a train of puffs at
    ``--release-height`` over ``--release-duration``.
    """
    dt_s = a.dt
    if a.explosion:
        rel_times = np.array([0.0])
        h = a.explosion["cloudTop"]
        n = a.cloud_layers
        heights = (np.arange(n) + 0.5) / n * h  # material spread ground -> top
        sz0 = np.full(n, max(h / (2 * n), a.source_sigma))
        sy0 = np.full(n, max(a.cloud_radius_frac * h, a.source_sigma))
    else:
        if a.release_duration <= 0:
            rel_times = np.array([0.0])
        else:
            n = int(min(math.ceil(a.release_duration * 3600 / dt_s), a.max_puffs))
            rel_times = np.arange(n) * (a.release_duration * 3600 / n)
        heights = np.array([a.release_height])
        sz0 = sy0 = np.array([a.source_sigma])
    n_times, n_layers = len(rel_times), len(heights)
    out: dict[str, list[float]] = {k: [] for k in ("t", "z", "sy", "sz", "m0", "vs", "pm")}
    for pm, frac, vs in bins:
        for ti in range(n_times):
            for li in range(n_layers):
                out["t"].append(rel_times[ti])
                out["z"].append(heights[li])
                out["sy"].append(sy0[li])
                out["sz"].append(sz0[li])
                out["m0"].append(a.release_mass * frac / (n_times * n_layers))
                out["vs"].append(vs)
                out["pm"].append(pm)
    return {k: np.array(v, float) for k, v in out.items()}


@dataclass
class PuffState:
    """Positions, sizes and masses of every puff during a run (arrays over puffs).

    ``m`` is the ground-coupled mass. With the residual layer on, ``mres`` is mass cut
    off above a falling mixing height, held between ``rbot`` and ``rtop``; ``dmix`` is
    the depth the coupled mass is mixed through and ``plid`` last step's mixing height.
    """

    x: FloatArray
    y: FloatArray
    z: FloatArray
    sy: FloatArray
    sz: FloatArray
    m: FloatArray
    released: BoolArray
    dmix: FloatArray
    plid: FloatArray
    mres: FloatArray
    rbot: FloatArray
    rtop: FloatArray

    @classmethod
    def initial(cls, puffs: dict[str, FloatArray]) -> PuffState:
        """Unreleased puffs at the source with their starting heights and sizes."""
        n = len(puffs["t"])
        return cls(
            x=np.zeros(n),
            y=np.zeros(n),
            z=puffs["z"].copy(),
            sy=puffs["sy"].copy(),
            sz=puffs["sz"].copy(),
            m=np.zeros(n),
            released=np.zeros(n, bool),
            dmix=np.full(n, np.nan),
            plid=np.full(n, np.nan),
            mres=np.zeros(n),
            rbot=np.full(n, np.inf),
            rtop=np.zeros(n),
        )


@dataclass
class _Budget:
    """Running totals of mass removed, kg."""

    dry: float = 0.0
    wet: float = 0.0
    spray: float = 0.0


def _residual_layer_step(
    st: PuffState, idx: IntArray, blh: FloatArray, lid: FloatArray, gz: FloatArray
) -> FloatArray:
    """Move mass between the mixed layer and the residual layer for one step.

    When the mixing height falls (around sunset), the share of a puff above the new
    top is cut off from the ground: it rides along with the puff but neither deposits
    nor adds to ground-level air until the mixing height grows back up into it. Rain
    still washes it out. Without this, a falling lid would fold the whole puff into
    the shallow night layer and overstate ground levels downwind.

    Updates ``st`` in place and returns the ground factor (1/m) for the active puffs.

    References
    ----------
    Stull (1988), the residual layer.
    """
    mi, dm, pl = st.m[idx], st.dmix[idx], st.plid[idx]
    lay = np.isfinite(dm)
    # puffs already mixed through the layer: uniform in [0, dm]
    fall = lay & (blh < dm)
    to_res = np.where(fall, mi * (1.0 - blh / np.where(lay, dm, 1.0)), 0.0)
    res_lo = np.where(fall, blh, np.inf)
    res_hi = np.where(fall, dm, 0.0)
    # puffs still Gaussian under a lid that fell since the last step
    gfall = (~lay) & np.isfinite(lid) & np.isfinite(pl) & (blh < pl)
    if gfall.any():
        s2 = math.sqrt(2) * st.sz[idx]
        zz = st.z[idx]
        keep = np.clip(
            _share_below(blh, zz, s2)
            / np.maximum(_share_below(np.where(gfall, pl, blh), zz, s2), 1e-30),
            0.0,
            1.0,
        )
        to_res = np.where(gfall, mi * (1.0 - keep), to_res)
        res_lo = np.where(gfall, blh, res_lo)
        res_hi = np.where(gfall, pl, res_hi)
    # residual mass mixes back down where the layer has grown into it
    mr, lo_r, hi_r = st.mres[idx], st.rbot[idx], st.rtop[idx]
    grow = (mr > 0) & (blh > lo_r)
    back = np.where(grow, mr * np.clip((blh - lo_r) / np.maximum(hi_r - lo_r, 1.0), 0.0, 1.0), 0.0)
    r_left = mr - back
    lo_after = np.where(grow, np.minimum(np.maximum(lo_r, blh), hi_r), lo_r)
    has_new = to_res > 0
    st.rbot[idx] = np.where(
        has_new, np.where(r_left > 0, np.minimum(lo_after, res_lo), res_lo), lo_after
    )
    st.rtop[idx] = np.where(has_new, np.maximum(np.where(r_left > 0, hi_r, 0.0), res_hi), hi_r)
    st.mres[idx] = r_left + to_res
    st.m[idx] = mi - to_res + back
    # coupled mass counts as mixed through the layer once the puff fills it
    mixed_now = np.isfinite(lid) & (st.sz[idx] > WELL_MIXED_SIGMA_Z * lid)
    dm = np.where(lay | mixed_now | (back > 0), blh, np.nan)
    st.dmix[idx] = dm
    st.plid[idx] = np.where(np.isfinite(lid), blh, np.nan)
    out: FloatArray = np.where(np.isfinite(dm), 1.0 / np.where(np.isfinite(dm), dm, 1.0), gz)
    return out


def _share_below(h: FloatArray, zz: FloatArray, s2: FloatArray) -> FloatArray:
    """Share of a ground-reflected Gaussian (center zz, sqrt(2) sigma = s2) between 0 and h."""
    out: FloatArray = 0.5 * (erf((h - zz) / s2) + erf((h + zz) / s2))
    return out


@dataclass
class SprayZone:
    """A water-spray zone at the source: a square of the same area as the wetted disk.

    ``lam`` is each puff's scavenging coefficient (1/s); spraying runs from ``t_on``
    to ``t_off`` seconds after the release, from the ground to ``height`` m.
    """

    half: float
    height: float
    lam: FloatArray
    t_on: float
    t_off: float
    n_sub: int = 24


def _spray_zone(
    a: argparse.Namespace, bins: Sequence[Bin], pm_all: FloatArray, rho_of: dict[float, float]
) -> SprayZone | None:
    """Set up ``--spray-flow``; also records ``a.spray_info`` for the page."""
    if not (getattr(a, "spray_flow", 0) and a.spray_flow > 0):
        return None
    area = math.pi * a.spray_radius**2
    flux = a.spray_flow / 1000.0 / 60.0 / area  # m3/s per m2 = m/s
    half = 0.5 * math.sqrt(area)
    lam_bin = {}
    for pm, _frac, _vs in bins:
        rho_b = rho_of.get(pm, a.density)
        d_p = (6.0 * pm / (math.pi * rho_b)) ** (1.0 / 3.0)
        lam_bin[pm] = spray_coefficient(d_p, rho_b, flux, a.spray_drop / 1000.0)
    lam_all = np.array([lam_bin[pm_] for pm_ in pm_all])
    a.spray_info = {
        "fluxMmH": flux * 3.6e6,
        "lambda": {f"{pm:.3g}": lam for pm, lam in lam_bin.items()},
        "efficiency": {
            f"{pm:.3g}": slinn_efficiency(
                (6.0 * pm / (math.pi * rho_of.get(pm, a.density))) ** (1 / 3),
                rho_of.get(pm, a.density),
                a.spray_drop / 1000.0,
            )
            for pm in lam_bin
        },
    }
    return SprayZone(
        half=half,
        height=a.spray_height,
        lam=lam_all,
        t_on=a.spray_start * 60.0,
        t_off=(a.spray_start + a.spray_duration) * 60.0,
    )


def _spray_capture(
    zone: SprayZone,
    st: PuffState,
    idx: IntArray,
    u: FloatArray,
    v: FloatArray,
    t: float,
    dt_s: float,
) -> FloatArray:
    """Mass (kg) the spray captures from each active puff this step.

    Each puff is sub-stepped along its path; at each sub-step the captured share is
    the overlap of the puff with the spray box times ``1 - exp(-lambda tau)``.
    """
    idx_z, idx_sz = st.z[idx], st.sz[idx]
    tau = dt_s / zone.n_sub
    fz = 0.5 * (
        erf((zone.height - idx_z) / (math.sqrt(2) * idx_sz)) - erf(-idx_z / (math.sqrt(2) * idx_sz))
    )
    fz += 0.5 * (
        erf((zone.height + idx_z) / (math.sqrt(2) * idx_sz)) - erf(idx_z / (math.sqrt(2) * idx_sz))
    )  # ground image
    fz = np.clip(fz, 0.0, 1.0)
    cap = np.zeros(len(idx))
    half = zone.half
    for k_ in range(zone.n_sub):
        tk = t + (k_ + 0.5) * tau
        if not (zone.t_on <= tk < zone.t_off):
            continue
        xs = st.x[idx] + u * (k_ + 0.5) * tau
        ys = st.y[idx] + v * (k_ + 0.5) * tau
        r2 = math.sqrt(2) * st.sy[idx]
        fx = 0.5 * (erf((half - xs) / r2) - erf((-half - xs) / r2))
        fy = 0.5 * (erf((half - ys) / r2) - erf((-half - ys) / r2))
        left = st.m[idx] - cap
        cap += left * fx * fy * fz * (1.0 - np.exp(-zone.lam[idx] * tau))
    return cap


def _hour_summary(
    st: PuffState,
    m0: FloatArray,
    lat0: float,
    lon0: float,
    coslat0: float,
    budget: _Budget,
) -> Json:
    """Puff positions, mass budget and mass-weighted centroid at the end of an hour."""
    mt = st.m + st.mres
    act = st.released & (mt > m0 * 1e-6)
    k = np.nonzero(act)[0]
    lat = lat0 + np.degrees(st.y[k] / R_EARTH)
    lon = lon0 + np.degrees(st.x[k] / (R_EARTH * coslat0))
    air = float(mt[st.released].sum())
    cen = None
    if air > 0 and len(k):
        w = mt[k] / mt[k].sum()
        cen = [round(float(np.dot(w, lat)), 5), round(float(np.dot(w, lon)), 5)]
    return {
        "puffs": [
            [
                round(float(a_), 5),
                round(float(b_), 5),
                round(float(s_), 1),
                round(float(f_), 4),
                round(float(h_), 1),
            ]
            for a_, b_, s_, f_, h_ in zip(lat, lon, st.sy[k], mt[k] / m0[k], st.z[k], strict=True)
        ],
        "released": float(m0[st.released].sum()),
        "airborne": air,
        "dry": budget.dry,
        "wet": budget.wet,
        "spray": budget.spray,
        "centroid": cen,
    }


def _turbulent_growth(
    a: argparse.Namespace,
    met: MetField,
    st: PuffState,
    idx: IntArray,
    where: tuple[FloatArray, FloatArray, FloatArray],
    cls: IntArray,
    blh: FloatArray,
    dt_s: float,
) -> tuple[FloatArray, FloatArray]:
    """Return new sigma_y, sigma_z for the puffs ``idx`` under ``--spread turbulence``.

    u*, L and w* from the weather at each puff (:func:`turbulence.scaling`), sigma_v
    and sigma_w at its height (:func:`turbulence.sigma_vw`), then one growth step
    (:func:`turbulence.grow`). Air temperature comes from the weather source when it
    has one, else the standard atmosphere's 288.15 K.
    """
    th, lat, lon = where
    u10 = np.hypot(met.sample("u", th, lat, lon), met.sample("v", th, lat, lon))
    t_air = met.sample("t2", th, lat, lon) if "t2" in met.f else T_AIR_DEFAULT
    u_star, obukhov, w_star = turbulence_scaling(
        u10,
        met.sample("sw", th, lat, lon),
        met.sample("cloud", th, lat, lon),
        blh,
        LAND_USE[getattr(a, "land_use", "grass")][0],
        t_air,
    )
    sv, sw = sigma_vw(
        u_star,
        obukhov,
        w_star,
        st.z[idx],
        blh,
        cls,
        getattr(a, "sigma_v_min", SIGMA_V_MIN_DEFAULT),
    )
    return turbulent_grow(
        st.sy[idx],
        st.sz[idx],
        sv,
        sw,
        obukhov > 0,
        dt_s,
        getattr(a, "spread_averaging", AVERAGING_DEFAULT_MIN),
    )


def run_model(  # noqa: PLR0915 - one time step, kept in one place on purpose
    a: argparse.Namespace,
    met: MetField,
    bins: Sequence[Bin],
    lat0: float,
    lon0: float,
) -> tuple[list[Record], list[Json]]:
    """Run the puff model.

    Each time step: release due puffs; look up stability, mixing height, rain and the
    wind at each puff's transport height; grow sigma along the Briggs curves; settle;
    move mass to and from the residual layer; remove mass by dry deposition (Zhang et
    al. 2001, or a fixed velocity), rain and the optional spray; record what the
    gridder needs; advect.

    Parameters
    ----------
    a
        Parsed options (see :func:`parse_args`).
    met
        Weather for the run.
    bins
        [(particle mass kg, mass fraction, settling velocity m/s)].
    lat0, lon0
        Release location.

    Returns
    -------
    tuple
        Per-step records for :func:`grid_fields`, and one summary per hour.
    """
    dt_s = a.dt
    n_steps = round(a.hours * 3600 / dt_s)
    steps_per_hour = round(3600 / dt_s)
    t_off = (a.start - met.t0).total_seconds() / 3600.0  # start offset in met hours

    puffs = build_puffs(a, bins)
    rel_times, m0, vs_all, pm_all = puffs["t"], puffs["m0"], puffs["vs"], puffs["pm"]
    st = PuffState.initial(puffs)
    resid = getattr(a, "residual_layer", True)
    budget = _Budget()
    rho_of = getattr(a, "rho_of", {})
    rho_all = np.array([rho_of.get(pm_, a.density) for pm_ in pm_all])
    d_all = (6.0 * pm_all / (math.pi * rho_all)) ** (1.0 / 3.0)
    size_resolved = getattr(a, "vd_extra", None) is None  # Zhang or Emerson, not --vd-extra
    if size_resolved:
        sc_all = schmidt_number(d_all, rho_all)
    else:
        vd_all = vs_all + a.vd_extra
    coslat0 = math.cos(math.radians(lat0))
    spray = _spray_zone(a, bins, pm_all, rho_of)

    spread_turbulence = getattr(a, "spread", "briggs") == "turbulence"
    records: list[Record] = []
    hourly: list[Json] = []
    for step in range(n_steps):
        t = step * dt_s
        hour = step // steps_per_hour
        new = (~st.released) & (rel_times <= t + 1e-6)
        st.m[new] = m0[new]
        st.released |= new
        idx = np.nonzero(st.released & ((st.m + st.mres) > m0 * 1e-9))[0]
        if len(idx):
            lat = lat0 + np.degrees(st.y[idx] / R_EARTH)
            lon = lon0 + np.degrees(st.x[idx] / (R_EARTH * coslat0))
            th = np.full(len(idx), t_off + (t + 0.5 * dt_s) / 3600.0)
            cls = met.sample("stab", th, lat, lon, nearest=True).astype(int)
            blh = met.sample("blh", th, lat, lon)
            pr = met.sample("precip", th, lat, lon)
            zt = np.clip(np.maximum(st.z[idx], 0.5 * np.minimum(st.sz[idx], blh)), 10.0, 3000.0)
            u, v = transport_wind(met, th, lat, lon, zt, cls, blh)
            ds = np.maximum(np.hypot(u, v), 0.5) * dt_s
            if spread_turbulence:
                st.sy[idx], st.sz[idx] = _turbulent_growth(
                    a, met, st, idx, (th, lat, lon), cls, blh, dt_s
                )
            else:
                st.sy[idx] = grow_sigma(st.sy[idx], cls, ds, SY_C, SY_K, SY_E)
                st.sz[idx] = grow_sigma(st.sz[idx], cls, ds, SZ_C, SZ_K, SZ_E)
            st.z[idx] = np.maximum(st.z[idx] - vs_all[idx] * dt_s, 0.0)
            lid = np.where(st.z[idx] <= blh, blh, np.inf)
            gz = ground_factor(st.z[idx], st.sz[idx], lid)
            if resid:
                gz = _residual_layer_step(st, idx, blh, lid, gz)
            if size_resolved:
                u10 = np.hypot(met.sample("u", th, lat, lon), met.sample("v", th, lat, lon))
                vd_now = deposition_velocity(
                    d_all[idx],
                    vs_all[idx],
                    sc_all[idx],
                    u10,
                    a.land_use,
                    getattr(a, "deposition", "zhang"),
                )
            else:
                vd_now = vd_all[idx]
            kd = vd_now * gz
            kw = a.scavenging * pr
            inv_mass = 1.0 / pm_all[idx]
            zeros = np.zeros(len(idx))
            if spray and t + dt_s > spray.t_on and t < spray.t_off:
                cap = _spray_capture(spray, st, idx, u, v, t, dt_s)
                st.m[idx] -= cap
                budget.spray += float(cap.sum())
                budget.wet += float(cap.sum())
                # captured mass lands in the spray zone
                records.append(
                    (hour, zeros, zeros, np.full(len(idx), spray.half), zeros, cap, inv_mass, False)
                )
            mm = st.m[idx]
            lost = mm * (1.0 - np.exp(-(kd + kw) * dt_s))
            frac_dry = np.where(kd + kw > 0, kd / np.maximum(kd + kw, 1e-30), 1.0)
            budget.dry += float(np.sum(lost * frac_dry))
            budget.wet += float(np.sum(lost * (1 - frac_dry)))
            # Concentration uses mid-step mass; deposition is what fell this step.
            records.append(
                (
                    hour,
                    st.x[idx].copy(),
                    st.y[idx].copy(),
                    st.sy[idx].copy(),
                    (mm - 0.5 * lost) * gz * dt_s,
                    lost,
                    inv_mass,
                    (step + 1) % steps_per_hour == 0,
                )
            )
            st.m[idx] = mm - lost
            if resid and np.any(kw > 0):
                washed = st.mres[idx] * (1.0 - np.exp(-kw * dt_s))
                st.mres[idx] -= washed
                budget.wet += float(washed.sum())
                # washed-out residual lead lands under the puff like other wet deposition
                records.append(
                    (
                        hour,
                        st.x[idx].copy(),
                        st.y[idx].copy(),
                        st.sy[idx].copy(),
                        zeros,
                        washed,
                        inv_mass,
                        False,
                    )
                )
            st.x[idx] += u * dt_s
            st.y[idx] += v * dt_s
        if (step + 1) % steps_per_hour == 0:
            hourly.append(_hour_summary(st, m0, lat0, lon0, coslat0, budget))
    return records, hourly
