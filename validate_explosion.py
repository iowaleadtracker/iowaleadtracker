#!/usr/bin/env python3
"""Validate puff_dispersal.py for an industrial explosion.

The case is 5 t of material with a specific energy of 1.4-1.64 MJ/kg.

Checks
  1. Source term: energy, TNT equivalent, Church cloud-top height, for both
     ends of the energy range (and 5 short tons as well as 5 tonnes).
  2. Numerics vs analytic: the 5-layer explosion cloud in a steady wind with a
     non-settling tracer. The model's time-integrated ground concentration
     (sum of its hourly maps) is compared with the closed-form Gaussian puff
     result for each layer (ground + mixing-lid reflections).
  3. Mass conservation in real-weather runs: airborne + deposited = lofted
     mass, and the deposition map integrates to the deposited mass.
  4. Sensitivity of the outputs to the 1.4 vs 1.64 MJ/kg range, in a daytime
     (unstable) and a night-time (stable) case.
  5. Visualisation range: whether the values of interest fall inside the
     encoded and displayed colour range.
  6. Near-field resolution: the default whole-plume map vs a 5 km window
     (--extent-km), to show how much grid cells smooth the peak near the source.
  7. Threat-zone metric and HYSPLIT export: the running 60-min mean must lie
     between the clock-hour mean and the short-term peak everywhere, and the
     HYSPLIT CONTROL file must be structurally consistent.
  8. Material, multi-shot source, winds aloft and the wind-direction ensemble
     (no network needed): tracked mass, cloud height from one charge, exact
     interpolation through pressure-level winds, plume turning with the wind,
     and the uncertainty envelope containing the central run.

Usage:  python3 validate_explosion.py [--lat 39.74 --lon -104.99] [--html-dir DIR]
Needs network access to Open-Meteo for checks 3-5.
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import math
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

import puff_dispersal as puff
from dispersal.constants import KG_PER_LB, TNT_MJ_PER_KG
from dispersal.deposition import deposition_velocity, schmidt_number
from dispersal.dispersion import (
    PROFILE_P,
    SY_C,
    SY_E,
    SY_K,
    SZ_C,
    SZ_E,
    SZ_K,
    ground_factor,
    grow_sigma,
)
from dispersal.met import MetField, build_met, rotated_met, transport_wind
from dispersal.model import run_model
from dispersal.output import pack, write_html
from dispersal.particles import particle_properties
from dispersal.source_term import explosion_source

SIZES = "1pg:0.25,30pg:0.25,1ng:0.25,30ng:0.25"  # ~1-32 um at 1720 kg/m3
DENSITY = "1720"
LEVELS = [("35 µg/m³", 35e-9), ("150 µg/m³", 150e-9), ("1 mg/m³", 1e-6), ("10 mg/m³", 1e-5)]
DEP_LEVELS = [("1 mg/m²", 1e-6), ("100 mg/m²", 1e-4), ("1 g/m²", 1e-3)]
HOTSPOT_TOL_M = 1.5  # HotSpot reports whole meters
ANALYTIC_TOL = 0.15  # worst allowed model/analytic deviation beyond 5 km


def run(argv: list[str]) -> tuple[argparse.Namespace, dict[str, Any], float]:
    """Run the model on command-line arguments; return (args, payload, seconds)."""
    a = puff.parse_args(argv)
    t0 = time.time()
    out = puff.simulate(a, log=io.StringIO())
    return a, out, time.time() - t0


def check_source() -> bool:
    """Check 1: energy, TNT equivalent and Church cloud-top height, and HotSpot examples."""
    ok = True
    print("1. SOURCE TERM (Church: H_top = 76 W^0.25, W = lb TNT by energy)")
    print(f"   {'material':>14} {'MJ/kg':>6} {'energy GJ':>10} {'TNT kg':>8} {'cloud top m':>12}")
    rows = []
    for label, mass in (("5 t (tonnes)", 5000.0), ("5 short tons", 5 * 907.18474)):
        for e in (1.4, 1.64):
            s = explosion_source(mass, e)
            rows.append(s)
            print(
                f"   {label:>14} {e:6.2f} {s['energyJ'] / 1e9:10.2f} {s['tntKg']:8.0f} "
                f"{s['cloudTop']:12.0f}"
            )
    # HotSpot's published examples: 113 lb TNT -> 248 m, 40 lb -> 191 m
    for lb, ref in ((113, 248), (40, 191)):
        h = explosion_source(lb * KG_PER_LB * TNT_MJ_PER_KG / TNT_MJ_PER_KG, TNT_MJ_PER_KG)
        print(
            f"   check vs HotSpot example: {lb} lb TNT -> {h['cloudTop']:.0f} m (published {ref} m)"
        )
        ok &= abs(h["cloudTop"] - ref) < HOTSPOT_TOL_M
    lo, hi = rows[0]["cloudTop"], rows[1]["cloudTop"]
    print(
        f"   -> energy range changes cloud height by only {100 * (hi / lo - 1):.1f}% "
        f"(height ~ E^0.25)\n"
    )
    return ok


def check_analytic() -> float:
    """Check 2: model vs closed-form Gaussian puff; return the worst relative deviation."""
    print(
        "2. NUMERICS vs ANALYTIC (5-layer cloud, 5 m/s wind from W, class D, "
        "mixing height 800 m, non-settling tracer)"
    )
    argv = [
        "--lat",
        "40",
        "--lon",
        "-100",
        "--time",
        "2024-06-01T12:00Z",
        "--wind",
        "5@270",
        "--explosive-mass",
        "5t",
        "--specific-energy",
        "1.64",
        "--particle-mass",
        "1e-21",
        "--vd-extra",
        "0",
        "--scavenging",
        "0",
        "--hours",
        "8",
        "--grid",
        "500",
        "--wind-grid",
        "1",
        "--dt",
        "60",
    ]
    a, out, secs = run(argv)
    A = out["_arrays"]
    tic = A["conc"].sum(0) * 3600.0  # kg s / m3
    xc = 0.5 * (A["xe"][1:] + A["xe"][:-1])
    yc = 0.5 * (A["ye"][1:] + A["ye"][:-1])
    j = int(np.argmin(np.abs(yc)))
    ex = a.explosion
    n = a.cloud_layers
    hs = (np.arange(n) + 0.5) / n * ex["cloudTop"]
    sz0 = max(ex["cloudTop"] / (2 * n), a.source_sigma)
    sy0 = a.cloud_radius_frac * ex["cloudTop"]
    blh, cls = 800.0, np.array([3])
    u10, z_up = 5.0, 100.0
    u_up = u10 * 10 ** PROFILE_P[3]

    def wind(zt: float) -> float:
        if zt <= z_up:
            return float(u10 + math.log(max(zt, 10) / 10) / math.log(z_up / 10) * (u_up - u10))
        return float(u_up * (min(zt, blh) / z_up) ** PROFILE_P[3])

    print(f"   grid cell {A['dx']:.0f} m, run time {secs:.1f} s")
    print(f"   {'x km':>6} {'model':>11} {'analytic':>11} {'ratio':>6}")
    worst = 0
    for xkm in (5, 10, 20, 40, 80):
        i = int(np.argmin(np.abs(xc - xkm * 1000)))
        x = xc[i]
        total = 0.0
        for h in hs:
            sy = grow_sigma(np.array([sy0]), cls, np.array([x]), SY_C, SY_K, SY_E)[0]
            sz = grow_sigma(np.array([sz0]), cls, np.array([x]), SZ_C, SZ_K, SZ_E)[0]
            zt = min(max(h, 0.5 * min(sz, blh), 10), 3000)
            gz = ground_factor(np.array([h]), np.array([sz]), np.array([blh]))[0]
            total += a.release_mass / n * gz / (math.sqrt(2 * math.pi) * sy * wind(zt))
        r = tic[j, i] / total
        worst = max(worst, abs(r - 1))
        print(f"   {x / 1000:6.1f} {tic[j, i]:11.3e} {total:11.3e} {r:6.2f}")
    print(
        f"   -> worst deviation {100 * worst:.0f}% (units kg·s/m³ = time-integrated "
        f"concentration)\n"
    )
    return worst


def summarise(
    label: str, a: argparse.Namespace, out: dict[str, Any], secs: float
) -> dict[str, Any]:
    """Print a real-weather run's mass budget and zone sizes; return its key numbers."""
    A, H = out["_arrays"], out["hours"]
    last = H[-1]
    tot = a.release_mass
    budget = last["airborne"] + last["dry"] + last["wet"]
    dep_grid = A["dep"][-1].sum() * A["dx"] ** 2
    dep_model = last["dry"] + last["wet"]
    cell_km2 = (A["dx"] / 1000) ** 2
    hmax = [h["cmax"] for h in H]
    peak_h = int(np.argmax(hmax))
    xc = 0.5 * (A["xe"][1:] + A["xe"][:-1])
    yc = 0.5 * (A["ye"][1:] + A["ye"][:-1])
    R = np.hypot(*np.meshgrid(xc, yc)) / 1000
    print(f"   {label}")
    print(
        f"     weather {out['meta']['weather']}; hour-1 stability {H[0]['stab']}, "
        f"mixing height {H[0]['blh']} m, wind10 {H[0]['ws']} m/s, wind{out['meta']['zUp']:.0f} "
        f"{H[0]['wsUp']} m/s; run {secs:.1f} s; cell {A['dx']:.0f} m"
    )
    print(
        f"     mass budget after {a.hours} h: airborne {last['airborne'] / tot:6.1%}  "
        f"dry {last['dry'] / tot:6.1%}  wet {last['wet'] / tot:6.1%}  "
        f"sum {budget / tot:.6f}"
    )
    print(f"     deposition map integral / deposited mass = {dep_grid / dep_model:.6f}")
    print(
        f"     peak hourly-mean ground concentration {hmax[peak_h] * 1e9:,.1f} µg/m³ "
        f"(hour {peak_h + 1}); peak deposition {last['dmax'] * 1e3:,.2f} g/m²"
    )
    pk = [h["pmax"] for h in H]
    print(
        f"     peak {a.dt / 60:.0f}-min ground concentration {max(pk) * 1e9:,.1f} µg/m³ "
        f"(hour {int(np.argmax(pk)) + 1})"
    )
    cmax_all = A["conc"].max(0)
    pmax_all = A["peak"].max(0)
    for name, v in LEVELS:
        m = cmax_all >= v
        mp = pmax_all >= v
        print(
            f"     >= {name:>9}: hourly mean {m.sum() * cell_km2:7.1f} km² to "
            f"{R[m].max() if m.any() else 0:5.1f} km | {a.dt / 60:.0f}-min peak "
            f"{mp.sum() * cell_km2:7.1f} km² to {R[mp].max() if mp.any() else 0:5.1f} km"
        )
    for name, v in DEP_LEVELS:
        m = A["dep"][-1] >= v
        print(
            f"     deposition  >= {name:>9}: area {m.sum() * cell_km2:8.1f} km², "
            f"reaches {R[m].max() if m.any() else 0:6.1f} km"
        )
    m60 = A["m60"].max(0)
    for k, (name, v) in enumerate(LEVELS):
        m = m60 >= v
        if k == 0:
            print("     threat zones (max running 60-min mean):")
        print(
            f"       >= {name:>9}: {m.sum() * cell_km2:7.1f} km², reaches "
            f"{R[m].max() if m.any() else 0:5.1f} km"
        )
    return {
        "cmax": hmax[peak_h],
        "dmax": last["dmax"],
        "pmax": max(pk),
        "peak": A["peak"],
        "m60": A["m60"],
        "out": out,
        "args": a,
        "c150": (cmax_all >= 150e-9).sum() * cell_km2,
        "d1mg": (A["dep"][-1] >= 1e-6).sum() * cell_km2,
        "conc": A["conc"],
        "dep": A["dep"],
        "dx": A["dx"],
        "mass_ok": abs(budget / tot - 1) < 1e-6 and abs(dep_grid / dep_model - 1) < 1e-3,
    }


def _ratio(hi: dict[str, Any], lo: dict[str, Any], key: str) -> float:
    return float(hi[key] / lo[key]) if lo[key] else float("nan")


def check_weather(lat: float, lon: float, html_dir: str | None) -> dict[tuple[str, str], Any]:
    """Run checks 3-4: real-weather runs (needs network) and the energy sensitivity."""
    print(
        "3/4. REAL WEATHER (ERA5), 5 t lofted as 1-32 µm particles "
        f"({SIZES}, {DENSITY} kg/m³), 24 h"
    )
    cases = [("day", "2024-06-01T08:00-06:00"), ("night", "2024-06-02T01:00-06:00")]
    results = {}
    for cname, t in cases:
        for e in ("1.4", "1.64"):
            argv = [
                "--lat",
                str(lat),
                "--lon",
                str(lon),
                "--time",
                t,
                "--explosive-mass",
                "5t",
                "--specific-energy",
                e,
                "--particle-mass",
                SIZES,
                "--density",
                DENSITY,
                "--hours",
                "24",
            ]
            a, out, secs = run(argv)
            results[(cname, e)] = summarise(
                f"{cname} release {t}, {e} MJ/kg (cloud top {a.explosion['cloudTop']:.0f} m)",
                a,
                out,
                secs,
            )
            if html_dir and e == "1.64":
                path = Path(html_dir) / f"explosion_{cname}.html"
                write_html(out, path)
                print(f"     wrote {path}")
    print("\n   SENSITIVITY 1.64 vs 1.4 MJ/kg (ratio high/low)")
    for cname, _ in cases:
        lo, hi = results[(cname, "1.4")], results[(cname, "1.64")]
        print(
            f"     {cname:>5}: max hourly mean {_ratio(hi, lo, 'cmax'):.3f}, "
            f"max 2-min peak {_ratio(hi, lo, 'pmax'):.3f}, "
            f"max deposition {_ratio(hi, lo, 'dmax'):.3f}, "
            f"area >=150 µg/m³ {_ratio(hi, lo, 'c150'):.3f}, "
            f"area >=1 mg/m² {_ratio(hi, lo, 'd1mg'):.3f}"
        )
    return results


def check_display(results: dict[tuple[str, str], Any]) -> bool:
    """Check 5: the levels of interest fall inside the encoded colour range."""
    print("\n5. VISUALISATION RANGE")
    ok = True
    for (cname, e), r in results.items():
        for key, levels in (("conc", LEVELS), ("peak", LEVELS), ("dep", DEP_LEVELS)):
            arr = r[key]
            packed = pack(arr)
            hi, lo = packed["hi"], packed["lo"]
            shown_floor = hi - 5  # default 5 decades on screen
            inside = [n for n, v in levels if lo <= math.log10(v) <= hi]
            onscreen = [n for n, v in levels if shown_floor <= math.log10(v) <= hi]
            print(
                f"   {cname:>5} {e:>4} {key:>4}: encoded {10**lo:.1e}..{10**hi:.1e} "
                f"kg/m{'²' if key == 'dep' else '³'}; levels encoded {len(inside)}/"
                f"{len(levels)}, on default 5-decade scale {len(onscreen)}/{len(levels)} "
                f"(levels above the maximum never occur)"
            )
            ok &= len(inside) == len([v for _, v in levels if v <= 10**hi])
    return ok


def check_near_field(lat: float, lon: float, html_dir: str | None) -> None:
    """Check 6: how much the whole-plume grid smooths the near-source peak."""
    print("\n6. NEAR-FIELD RESOLUTION (day case, 1.64 MJ/kg, first 2 h)")
    base = [
        "--lat",
        str(lat),
        "--lon",
        str(lon),
        "--time",
        "2024-06-01T08:00-06:00",
        "--explosive-mass",
        "5t",
        "--specific-energy",
        "1.64",
        "--particle-mass",
        SIZES,
        "--density",
        DENSITY,
        "--dt",
        "60",
    ]
    out = {}
    for label, extra in (
        ("whole plume, 24 h", ["--hours", "24"]),
        ("5 km window, 2 h", ["--hours", "2", "--extent-km", "5"]),
    ):
        _, o, _ = run([*base, *extra])
        A, H = o["_arrays"], o["hours"]
        out[label] = (H[0]["cmax"], H[0]["pmax"], A["dx"])
        print(
            f"   {label:>18}: cell {A['dx']:5.0f} m  hour-1 max hourly mean "
            f"{H[0]['cmax'] * 1e9:8.1f} µg/m³, max 1-min peak {H[0]['pmax'] * 1e9:8.1f} µg/m³"
        )
        if html_dir and "window" in label:
            path = Path(html_dir) / "explosion_nearfield.html"
            write_html(o, path)
            print(f"     wrote {path}")
    (c1, p1, _), (c2, p2, _) = out.values()
    print(
        f"   -> coarse map understates the near-source hourly mean by {c2 / c1:.1f}x and the "
        f"short-term peak by {p2 / p1:.1f}x; use --extent-km for near-field numbers"
    )


def check_zones_and_hysplit(results: dict[tuple[str, str], Any]) -> bool:
    """Check 7: 60-min metric bounded by hourly mean and peak; HYSPLIT CONTROL consistent."""
    print("\n7. THREAT-ZONE METRIC AND HYSPLIT EXPORT")
    ok = True
    for (cname, e), r in results.items():
        m60, conc, peak = r["m60"].max(0), r["conc"].max(0), r["peak"].max(0)
        tol = 1e-9 * peak.max()
        lo_ok = bool(np.all(m60 >= conc - tol))
        hi_ok = bool(np.all(m60 <= peak + tol))
        ok &= lo_ok and hi_ok
        print(
            f"   {cname:>5} {e:>4}: hourly mean <= 60-min max {lo_ok}; 60-min max <= peak {hi_ok}"
        )
    r = results[("day", "1.64")]
    ctl = r["out"]["meta"]["hysplit"]["CONTROL"].strip().split("\n")
    a = r["args"]
    i = 0
    i += 1  # start time
    nsrc = int(ctl[i])
    i += 1 + nsrc
    tops = [float(ctl[2 + k].split()[2]) for k in range(nsrc)]
    i += 3  # hours, vertical motion, model top
    nmet = int(ctl[i])
    i += 1 + 2 * nmet
    npol = int(ctl[i])
    i += 1
    total = sum(float(ctl[i + 4 * k + 1]) * float(ctl[i + 4 * k + 2]) for k in range(npol))
    i += 4 * npol
    i += 1 + 5 + 1 + 1 + 3  # grids, grid def (5), levels count+heights, sampling
    ndep = int(ctl[i])
    i += 1 + 5 * ndep
    struct_ok = (
        i == len(ctl)
        and ndep == npol == len(a.particle_mass)
        and nsrc == 2
        and abs(total / a.release_mass - 1) < 1e-4
        and abs(tops[1] - a.explosion["cloudTop"]) < 1
    )
    ok &= struct_ok
    print(
        f"   CONTROL: {len(ctl)} lines, {nsrc} source heights {tops}, {npol} pollutants, "
        f"emitted {total:.0f} kg, met {ctl[2 + nsrc + 3 + 2]} -> consistent {struct_ok}"
    )
    return ok


def _check_material() -> bool:
    """Check (a), the material preset: lead mass and cloud height from ONE of two charges."""
    a = puff.parse_args(
        [
            *("--lat", "40"),
            *("--lon", "-100"),
            *("--material", "lead-azide"),
            *("--explosive-mass", "5t"),
            *("--shots", "2"),
            *("--confinement", "earth-covered"),
            *("--airborne-fraction", "0.5"),
            *("--wind", "5@180"),
        ]
    )
    lead = 5000 * 207.2 / 291.24 * 0.5
    top = 0.5 * 76.0 * (2500 * a.specific_energy / TNT_MJ_PER_KG / KG_PER_LB) ** 0.25
    t = abs(a.release_mass - lead) < 1e-6 and abs(a.explosion["cloudTop"] - top) < 1e-6
    d_um = [(6 * m / (math.pi * a.density)) ** (1 / 3) * 1e6 for m, _ in a.particle_mass]
    t &= all(abs(x - y) < 1e-6 for x, y in zip(d_um, (1, 3, 10, 30), strict=True))
    print(
        f"   lead-azide preset: {a.release_mass:.1f} kg lead (expect {lead:.1f}), cloud top "
        f"{a.explosion['cloudTop']:.1f} m (expect {top:.1f}), diameters "
        f"{[round(x, 2) for x in d_um]} um -> {t}"
    )
    return bool(t)


def _uniform(v: float) -> np.ndarray:
    return np.full((4, 1, 1), float(v))


def _check_winds_aloft() -> bool:
    """Check (b), pressure-level winds: a made-up profile is reproduced at its levels."""
    f = {
        "u": _uniform(0),
        "v": _uniform(5),
        "u_up": _uniform(0),
        "v_up": _uniform(8),
        "ws": _uniform(5),
        "wd": _uniform(180),
        "cloud": _uniform(100),
        "sw": _uniform(0),
        "precip": _uniform(0),
        "stab": np.full((4, 1, 1), 3),
        "blh": _uniform(800),
        "zl0": _uniform(400),
        "ul0": _uniform(3),
        "vl0": _uniform(12),
        "zl1": _uniform(1000),
        "ul1": _uniform(6),
        "vl1": _uniform(18),
    }
    met = MetField(
        dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc),
        np.array([40.0]),
        np.array([-100.0]),
        f,
        100.0,
        2,
        ["A", "B"],
    )
    zs = np.array([10.0, 100.0, 250.0, 400.0, 700.0, 1000.0, 2500.0])
    args = (
        np.full(7, 1.0),
        np.full(7, 40.0),
        np.full(7, -100.0),
        zs,
        np.full(7, 3),
        np.full(7, 800.0),
    )
    u, v = transport_wind(met, *args)
    exp_v = [5, 8, 10, 12, 15, 18, 18]
    exp_u = [0, 0, 1.5, 3, 4.5, 6, 6]
    t = bool(np.allclose(v, exp_v) and np.allclose(u, exp_u))
    print(
        f"   winds aloft at {zs.astype(int).tolist()} m: v = {np.round(v, 2).tolist()} "
        f"(expect {exp_v}) -> {t}"
    )
    return t


def _check_ensemble() -> tuple[bool, dict[str, Any]]:
    """Check (c): turning the wind turns the plume; the envelope contains the central run.

    Returns the pass flag and the ensemble run's arrays (used by the snapshot check).
    """
    base = [
        *("--lat", "40"),
        *("--lon", "-100"),
        *("--time", "2024-06-01T12:00Z"),
        *("--wind", "6@180"),
        *("--explosive-mass", "1t"),
        *("--particle-diameter", "3um"),
        *("--hours", "3"),
        *("--dt", "120"),
    ]
    a, out, _ = run([*base, "--ensemble", "5", "--dir-spread", "10"])
    met0 = build_met(40, -100, a.start, 3, 1, (6.0, 180.0))[1]
    bins = [(pm, fr, particle_properties(pm, a.density)[1]) for pm, fr in a.particle_mass]
    _, hr = run_model(a, rotated_met(met0, 8.0), bins, 40.0, -100.0)
    c = hr[-1]["centroid"]
    brg = math.degrees(math.atan2((c[1] + 100) * math.cos(math.radians(40)), c[0] - 40)) % 360
    t = abs(brg - 8.0) < 0.3
    print(f"   wind turned from 180 to 188 deg: plume bearing {brg:.2f} deg (expect 8) -> {t}")
    A = out["_arrays"]
    inside = all(
        bool(np.all(A["env_" + k] >= A[k] - 1e-12 * A[k].max()))
        for k in ("conc", "peak", "m60", "dep")
    )
    X, Y = np.meshgrid(0.5 * (A["xe"][1:] + A["xe"][:-1]), 0.5 * (A["ye"][1:] + A["ye"][:-1]))
    m = (A["env_dep"][-1] > 1e-3 * A["env_dep"][-1].max()) & (np.hypot(X, Y) > 20e3)
    ang = np.degrees(np.arctan2(X[m], Y[m]))
    # filled wedge: at 60-70 km every 1-degree bearing between -9 and +9 must be covered
    ring = (np.hypot(X, Y) > 60e3) & (np.hypot(X, Y) < 70e3) & (A["env_dep"][-1] > 0)
    ring_ang = np.degrees(np.arctan2(X[ring], Y[ring]))
    lev = 1e-2 * A["env_dep"][-1][ring].max()
    filled = all(
        ((np.abs(ring_ang - b) < 0.6) & (A["env_dep"][-1][ring] > lev)).any() for b in range(-9, 10)
    )
    print(
        f"   envelope >= central everywhere: {inside}; envelope spans bearings "
        f"{ang.min():.0f} to {ang.max():.0f} deg with no gaps at 60-70 km: {filled}"
    )
    return t and inside and filled, A


def _check_deposition() -> bool:
    """Check (e), size-resolved dry deposition over grass (Zhang et al. 2001)."""
    ds = np.array([0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0]) * 1e-6
    vg = np.array([particle_properties(9500 * math.pi * d**3 / 6, 9500)[1] for d in ds])
    sc = schmidt_number(ds, 9500.0)
    vd5 = deposition_velocity(ds, vg, sc, np.full(7, 5.0), "grass")
    vd10 = deposition_velocity(ds, vg, sc, np.full(7, 10.0), "grass")
    k = int(np.argmin(vd5))
    t = bool(
        np.all(vd5 >= vg)
        and 0.3e-6 <= ds[k] <= 3e-6
        and np.all(vd10 >= vd5 - 1e-12)
        and 2e-4 < vd5[k] < 5e-3
    )
    print(
        f"   Zhang deposition, grass, 5 m/s: {np.round(vd5 * 100, 3).tolist()} cm/s for "
        f"{(ds * 1e6).tolist()} um; minimum at {ds[k] * 1e6:g} um, never below settling, "
        f"rises with wind -> {t}"
    )
    return t


def _respirable_share(argv: list[str]) -> tuple[float, argparse.Namespace]:
    c = puff.parse_args(argv)
    return sum(f for m, f in c.particle_mass if c.rho_of[m] == c.density), c


def _check_release_cases() -> bool:
    """Check the release cases: the TNT-equivalent rule and the 20-percent case."""
    lead_azide = [*("--lat", "40"), *("--lon", "-100"), *("--material", "lead-azide")]
    resp, c = _respirable_share(
        [
            *lead_azide,
            *("--explosive-mass", "5t"),
            *("--specific-energy", "1.64"),
            *("--shots", "2"),
            *("--release-case", "tnt-equivalent"),
            *("--wind", "5@180"),
        ]
    )
    exp = (5000 * 1.64 / TNT_MJ_PER_KG) / (5000 * 207.2 / 291.24)
    resp2, _ = _respirable_share(
        [
            *lead_azide,
            *("--explosive-mass", "5t"),
            *("--release-case", "20-percent"),
            *("--wind", "5@180"),
        ]
    )
    t = (
        abs(resp - exp) < 1e-9
        and abs(resp2 - 0.2) < 1e-9
        and abs(sum(f for _, f in c.particle_mass) - 1) < 1e-9
    )
    print(
        f"   release cases: TNT-equivalent rule gives {resp:.1%} respirable (expect {exp:.1%}); "
        f"20-percent gives {resp2:.0%}; shares sum to 1 -> {t}"
    )
    return t


def check_new_features() -> bool:
    """Check 8: material, shots, winds aloft, ensemble, deposition, release cases (offline)."""
    print("8. MATERIAL, SHOTS, WINDS ALOFT, ENSEMBLE")
    ok = _check_material()
    ok &= _check_winds_aloft()
    ens_ok, A = _check_ensemble()
    ok &= ens_ok
    ok &= _check_deposition()
    ok &= _check_release_cases()
    # (d) snapshot field equals the peak field at the instant it is taken (bounded by it)
    t = bool(np.all(A["snap"] <= A["peak"] + 1e-12 * A["peak"].max()))
    print(f"   end-of-hour snapshot never exceeds the in-hour peak: {t}\n")
    return ok and t


def main() -> None:
    """Run the checks and exit 0 if they all pass."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--lat", type=float, default=39.74)
    ap.add_argument("--lon", type=float, default=-104.99)
    ap.add_argument("--html-dir", default=None, help="also write the 1.64 MJ/kg maps here")
    ap.add_argument("--offline", action="store_true", help="only checks 1-2 (no network)")
    a = ap.parse_args()
    passed = check_source()
    worst = check_analytic()
    passed &= worst < ANALYTIC_TOL
    passed &= check_new_features()
    if not a.offline:
        results = check_weather(a.lat, a.lon, a.html_dir)
        passed &= all(r["mass_ok"] for r in results.values())
        passed &= check_display(results)
        passed &= check_zones_and_hysplit(results)
        check_near_field(a.lat, a.lon, a.html_dir)
    print("\nRESULT:", "PASS" if passed else "FAIL")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
