#!/usr/bin/env python3
r"""Hourly particle dispersal maps from a Gaussian puff model: the command line.

Given a release location (lat/lon), a start date-time and a particle mass, this
script:

  1. pulls hourly wind, cloud, radiation, precipitation and boundary-layer
     height for a 5x5 grid of points around the source from Open-Meteo
     (historical ERA5 reanalysis for past dates, the forecast model otherwise;
     no API key needed),
  2. derives the particle's diameter and gravitational settling velocity from
     its mass and density,
  3. runs a Lagrangian Gaussian puff model (Pasquill-Gifford / Briggs
     dispersion, power-law wind profile, tilted-puff settling, dry and wet
     deposition with source depletion, mixing-height reflection),
  4. writes ONE self-contained HTML file: an interactive map with an hour
     slider showing hourly-average ground-level air concentration and
     cumulative deposition, puff positions, wind vectors, and a per-hour
     mass budget. All data and code are embedded; only the optional basemap
     tiles are fetched when the file is viewed.

The model itself is in the ``dispersal`` package, one module per topic; this file
parses the options, runs the weather models and ensemble members, and writes the page.

Requires Python 3.10+ and numpy.

Example
-------
    python3 puff_dispersal.py --lat 39.74 --lon -104.99 \
        --time 2024-06-01T14:00Z --particle-mass 25ng --hours 24

Run with --help for every option. See MODEL.md for the model description and
its limitations: this is a screening tool, not a regulatory model.
"""

from __future__ import annotations

import argparse
import datetime as dt
import math
import sys
from pathlib import Path
from typing import TYPE_CHECKING, TextIO, TypeAlias

import numpy as np

from dispersal.constants import CLASSES, R_EARTH, TNT_MJ_PER_KG
from dispersal.deposition import LAND_USE, zhang_deposition_velocity, zhang_surface_terms
from dispersal.grid import angular_smear, grid_fields
from dispersal.met import (
    MET_CACHE,
    MODEL_RESIDUAL_DEG,
    WEATHER_ENSEMBLE,
    MetField,
    build_met,
    rotated_met,
)
from dispersal.model import run_model
from dispersal.output import hysplit_files, pack, write_html
from dispersal.particles import particle_properties
from dispersal.source_term import (
    COARSE_BINS,
    COARSE_DENSITY,
    CONFINEMENT,
    FINE_CASES,
    MATERIALS,
    RELEASE_CASES,
    SIZE_PRESETS,
    TNT_EQUIVALENT_CASE,
    TWENTY_PERCENT_CASE,
    explosion_source,
)
from dispersal.units import (
    parse_areal,
    parse_conc,
    parse_diam_dist,
    parse_mass,
    parse_size_dist,
    parse_time,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from dispersal.types import Bin, FloatArray, Json, Record


def _add_release_args(p: argparse.ArgumentParser) -> None:
    """Location, time, particles, material and the release itself."""
    p.add_argument("--lat", type=float, required=True, help="release latitude (deg)")
    p.add_argument("--lon", type=float, required=True, help="release longitude (deg)")
    p.add_argument(
        "--time",
        default="now",
        help="release start, ISO 8601 (e.g. 2024-06-01T14:00Z or "
        "2024-06-01T08:00-06:00). Naive = UTC.",
    )
    p.add_argument(
        "--particle-mass",
        type=parse_size_dist,
        default=None,
        help="mass of ONE particle with unit (kg g mg ug ng pg; bare number = kg), "
        "or a size distribution 'MASS:FRACTION,...' e.g. "
        "'1pg:0.25,30pg:0.25,1ng:0.25,30ng:0.25' (default 10ng)",
    )
    p.add_argument(
        "--particle-diameter",
        type=parse_diam_dist,
        default=None,
        help="particle size by diameter instead of mass: '3um' or "
        "'1um:0.25,10um:0.75' (nm um mm; bare number = um)",
    )
    p.add_argument(
        "--size-preset",
        choices=sorted(SIZE_PRESETS),
        default=None,
        help="a named size distribution: "
        + "; ".join(f"{k} = {v[0]}" for k, v in sorted(SIZE_PRESETS.items())),
    )
    p.add_argument(
        "--density",
        type=float,
        default=None,
        help="particle density kg/m3 (default 1000 = aerodynamic-equivalent, or "
        "the preset's value; pollen ~1000-1200, mineral dust ~2650)",
    )
    p.add_argument(
        "--material",
        choices=sorted(MATERIALS),
        default=None,
        help="material preset: sets what is tracked (e.g. lead in lead azide), "
        "its share of the material, energy, density, sizes, units and "
        "benchmark levels; any option given explicitly still wins",
    )
    p.add_argument(
        "--tracked-fraction",
        type=float,
        default=None,
        help="mass fraction of the material that is the tracked substance "
        "(e.g. 0.711 for lead in lead azide; default 1)",
    )
    p.add_argument(
        "--tracked-name", default=None, help="name of the tracked substance for labels, e.g. lead"
    )
    p.add_argument(
        "--release-mass",
        type=parse_mass,
        default=None,
        help="TOTAL particulate mass released (scales concentrations). "
        "Default 1 kg, or explosive mass x airborne fraction",
    )
    p.add_argument(
        "--release-duration",
        type=float,
        default=1.0,
        help="hours over which the mass is released (0 = one instantaneous puff)",
    )
    p.add_argument("--release-height", type=float, default=10.0, help="release height (m)")
    p.add_argument("--source-sigma", type=float, default=5.0, help="initial puff size sigma (m)")


def _add_explosion_args(p: argparse.ArgumentParser) -> None:
    """Add the options for an instantaneous buoyant-cloud (explosion) source."""
    g = p.add_argument_group("explosion source (instantaneous buoyant cloud)")
    g.add_argument(
        "--explosive-mass",
        type=parse_mass,
        default=None,
        help="mass of material that detonates, e.g. 5ton (U.S. tons) or 5t "
        "(metric tons); switches to an "
        "explosion source",
    )
    g.add_argument(
        "--specific-energy",
        type=float,
        default=None,
        help="energy released per kg of material, MJ/kg (default: the material "
        "preset's value, else TNT = 4.184)",
    )
    g.add_argument(
        "--shots",
        type=int,
        default=1,
        help="number of equal charges fired together at the site: the material "
        "is the total, the cloud height comes from one charge",
    )
    g.add_argument(
        "--confinement",
        choices=sorted(CONFINEMENT),
        default="open",
        help="open = open-air surface burst; earth-covered = charge inside an "
        "earth-covered or bermed structure, which halves the cloud height "
        "unless --church-factor is given (screening assumption)",
    )
    g.add_argument(
        "--airborne-fraction",
        type=float,
        default=1.0,
        help="fraction of the tracked substance lofted as particulate (1.0 = bounding case)",
    )
    g.add_argument(
        "--release-case",
        choices=sorted(RELEASE_CASES),
        default=None,
        help="documented reference case for the respirable share: "
        # argparse formats help with %, so the cases' "20%" and "7%" must be escaped
        + "; ".join(f"{k} = {v}" for k, v in sorted(RELEASE_CASES.items())).replace("%", "%%"),
    )
    g.add_argument(
        "--respirable-fraction",
        type=float,
        default=None,
        help="share of the lofted tracked substance that is respirable (fine "
        "'fume' sizes); the rest goes into coarse 30 and 100 um particles "
        "on soil and debris",
    )
    g.add_argument(
        "--cloud-layers",
        type=int,
        default=5,
        help="puff layers spreading the material from ground to cloud top",
    )
    g.add_argument(
        "--cloud-radius-frac",
        type=float,
        default=0.25,
        help="initial horizontal sigma as a fraction of cloud-top height",
    )
    g.add_argument(
        "--church-factor",
        type=float,
        default=None,
        help="multiplier on the Church cloud-top height (default 1, or the --confinement value)",
    )


def _add_run_args(p: argparse.ArgumentParser) -> None:
    """Run length, time step, map grid and weather."""
    p.add_argument("--hours", type=int, default=24, help="hours to simulate")
    p.add_argument("--dt", type=float, default=120.0, help="model time step (s); divides 3600")
    p.add_argument("--max-puffs", type=int, default=600, help="cap on puffs released")
    p.add_argument("--grid", type=int, default=260, help="map cells along the longer side")
    p.add_argument(
        "--extent-km",
        type=float,
        default=None,
        help="fix the map to a square of this half-width around the source "
        "(finer cells for near-field detail); default fits the whole plume",
    )
    p.add_argument(
        "--wind-grid",
        type=int,
        default=5,
        help="NxN Open-Meteo points for the wind field (1 = source only)",
    )
    p.add_argument(
        "--no-residual-layer",
        dest="residual_layer",
        action="store_false",
        help="let a falling mixing height fold the whole puff into the shallow "
        "layer (the old behavior; overstates ground levels after sunset)",
    )
    p.add_argument(
        "--no-pressure-levels",
        action="store_true",
        help="do not use pressure-level winds aloft; extend the 100/120 m wind "
        "with the stability power law instead",
    )
    p.add_argument(
        "--weather-model",
        default="ensemble",
        help="'ensemble' (default) runs the built-in set of forecast models: the "
        "first is shown and the rest feed the uncertainty view. Or give "
        "'best-match' for Open-Meteo's single default, or one or more "
        "Open-Meteo model names separated by commas (first one is shown). "
        "Built-in set: "
        + ", ".join(WEATHER_ENSEMBLE)
        + ". Historical dates and --wind always use a single source",
    )
    p.add_argument(
        "--ensemble",
        type=int,
        default=1,
        help="number of wind-direction members (odd, e.g. 5). The map shows the "
        "central run; an 'uncertainty' toggle shows the highest value any "
        "member gives",
    )
    p.add_argument(
        "--dir-spread",
        type=float,
        default=10.0,
        help="ensemble members turn the whole wind field by up to +/- this many degrees",
    )
    p.add_argument(
        "--met-cache",
        default=None,
        metavar="FILE",
        help="store Open-Meteo responses in this JSON file and reuse them on "
        "later runs (reproducible, and spares the API)",
    )
    p.add_argument(
        "--as-of",
        default=None,
        metavar="TIME",
        help="treat this ISO 8601 time as 'now' when choosing forecast or archive weather; "
        "set it to when a --met-cache was filled to rebuild the same maps on a later date",
    )
    p.add_argument(
        "--wind",
        default=None,
        help="skip Open-Meteo and use a constant wind 'SPEED@DIR' "
        "(m/s, direction blowing FROM in degrees), e.g. 5@270",
    )
    p.add_argument(
        "--vd-extra",
        type=float,
        default=None,
        help="use a fixed dry deposition velocity added to settling (m/s) instead "
        "of the size-resolved Zhang et al. (2001) scheme",
    )
    p.add_argument(
        "--land-use",
        choices=sorted(LAND_USE),
        default="grass",
        help="surface type for the Zhang et al. (2001) dry-deposition scheme",
    )


def _add_removal_args(p: argparse.ArgumentParser) -> None:
    """Water spray at the source and rain."""
    g2 = p.add_argument_group("water spray at the source")
    g2.add_argument(
        "--spray-flow",
        type=float,
        default=0.0,
        help="total water flow sprayed at the site, L/min (0 = no spray)",
    )
    g2.add_argument(
        "--spray-radius",
        type=float,
        default=50.0,
        help="radius of the wetted zone around the source, m",
    )
    g2.add_argument("--spray-height", type=float, default=30.0, help="height the spray reaches, m")
    g2.add_argument("--spray-drop", type=float, default=1.0, help="drop diameter, mm")
    g2.add_argument(
        "--spray-start",
        type=float,
        default=0.0,
        help="minutes after the release that spraying starts",
    )
    g2.add_argument("--spray-duration", type=float, default=60.0, help="minutes of spraying")
    p.add_argument(
        "--rain",
        type=float,
        default=None,
        metavar="MM_PER_H",
        help="override precipitation everywhere with this rate (mm/h), e.g. to "
        "test wet removal; default uses the weather data",
    )
    p.add_argument(
        "--scavenging",
        type=float,
        default=1e-4,
        help="wet scavenging coefficient per mm/h of rain (1/s per mm/h)",
    )


def _add_display_args(p: argparse.ArgumentParser) -> None:
    """Levels of concern, color scale, page settings and outputs."""
    p.add_argument(
        "--loc",
        default=None,
        help="three levels of concern (low to high) for the yellow/orange/red "
        "threat zones, per m3 unless given e.g. as 0.2ug/cm3; "
        "editable in the page too (default 0.15mg,5mg,15mg or the "
        "material preset's)",
    )
    p.add_argument(
        "--loc-labels", default=None, help="'|'-separated names for the three levels of concern"
    )
    p.add_argument(
        "--dep-loc",
        default=None,
        help="three deposition levels (low to high) for the threat-zone view, "
        "e.g. 5ug/ft2,40ug/ft2,100ug/ft2 (per m2 if no area unit; default "
        "1mg,10mg,100mg per m2 or the material preset's)",
    )
    p.add_argument(
        "--dep-loc-labels", default=None, help="'|'-separated names for the three deposition levels"
    )
    p.add_argument(
        "--scale-max",
        type=parse_conc,
        default=None,
        help="fix the top of the air-concentration color scale, e.g. "
        "0.2ug/cm3 or 200mg (per m3); default is the run's maximum",
    )
    p.add_argument(
        "--scale-min",
        type=parse_conc,
        default=None,
        help="minimum air concentration to show, e.g. 0.2ug/cm3: the color "
        "scale starts here and runs --decades above it; lower values "
        "are hidden (toggle in page)",
    )
    p.add_argument(
        "--home-url",
        default=None,
        help="site the map belongs to; shown in a banner when the map page is "
        "opened on its own instead of inside that site",
    )
    p.add_argument(
        "--legend-note",
        default=None,
        help="scenario line at the bottom of the map legend, e.g. the case and blast "
        "time, so a screenshot of the map says what it shows",
    )
    p.add_argument(
        "--units",
        choices=["mass", "ugm3", "ugft2", "cm3", "count"],
        default=None,
        help="initial display units: mass per m3 (auto prefix), ug/m3, ugft2 "
        "(air in ug/m3, deposition in ug/ft2), ug/cm3, or particle count",
    )
    p.add_argument(
        "--zone-metric",
        choices=["m60", "peak", "dep"],
        default=None,
        help="initial threat-zone measure: m60 (max 60-min air average), peak "
        "(max short-term air peak) or dep (cumulative deposition); default "
        "from the material, else m60",
    )
    p.add_argument(
        "--decades",
        type=int,
        default=5,
        help="initial color-scale range in decades (2-8, adjustable in page)",
    )
    p.add_argument(
        "--hysplit",
        default=None,
        metavar="DIR",
        help="also write HYSPLIT CONTROL and SETUP.CFG files for the same "
        "scenario into DIR (they are always downloadable from the page)",
    )
    p.add_argument("--title", default=None, help="title shown in the HTML")
    p.add_argument("-o", "--out", default=None, help="output HTML path")


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser (options only; :func:`parse_args` resolves defaults)."""
    p = argparse.ArgumentParser(
        description="Hourly particle dispersal map (Gaussian puff model) as a "
        "self-contained HTML file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    _add_release_args(p)
    _add_explosion_args(p)
    _add_run_args(p)
    _add_removal_args(p)
    _add_display_args(p)
    return p


def _resolve_material(a: argparse.Namespace, mat: Json, p: argparse.ArgumentParser) -> None:
    """Tracked substance, its share of the material, and the material's energy."""
    a.tracked_name = a.tracked_name or mat.get("tracked_name")
    if a.tracked_fraction is None:
        a.tracked_fraction = mat.get("tracked_fraction", 1.0)
    if not 0 < a.tracked_fraction <= 1:
        p.error("--tracked-fraction must be between 0 and 1")
    if a.specific_energy is None:
        a.specific_energy = mat.get("specific_energy", TNT_MJ_PER_KG)


def _resolve_sizes(a: argparse.Namespace, mat: Json) -> None:
    """Particle sizes: explicit diameters > explicit masses > a named preset > 10 ng."""
    explicit = a.particle_diameter is not None or a.particle_mass is not None
    preset = a.size_preset or (None if explicit else mat.get("size_preset"))
    if a.density is None:
        a.density = (SIZE_PRESETS[preset][2] if preset else None) or mat.get("density") or 1000.0

    def to_mass(d: float) -> float:
        return float(a.density * math.pi * d**3 / 6.0)

    if a.particle_diameter is not None:
        a.particle_mass = [(to_mass(d), f) for d, f in a.particle_diameter]
        a.size_note = "sizes given by diameter"
    elif a.particle_mass is not None and not a.size_preset:
        a.size_note = "sizes given by particle mass"
    elif preset:
        a.particle_mass = [(to_mass(d * 1e-6), f) for d, f in SIZE_PRESETS[preset][1]]
        tot = sum(f for _, f in a.particle_mass)
        a.particle_mass = [(m_, f / tot) for m_, f in a.particle_mass]
        a.size_note = f"'{preset}' preset: {SIZE_PRESETS[preset][0]}"
    else:
        a.particle_mass = parse_size_dist("10ng")
        a.size_note = "default single size"
    a.rho_of = {m_: a.density for m_, _ in a.particle_mass}


def _resolve_display(a: argparse.Namespace, mat: Json) -> None:
    """Display units, levels of concern and their labels."""
    a.units = a.units or mat.get("units") or "mass"
    a.loc = a.loc or mat.get("loc") or "0.15mg,5mg,15mg"
    a.loc_labels = (
        a.loc_labels
        if a.loc_labels is not None
        else (mat.get("loc_labels") if "loc" in mat and a.loc == mat["loc"] else None)
    )
    if a.loc_labels is None:
        a.loc_labels = (
            "PM10 24-h NAAQS|OSHA respirable dust PEL (PNOR)|OSHA total dust PEL (PNOR)"
            if a.loc == "0.15mg,5mg,15mg"
            else "||"
        )
    a.dep_loc = a.dep_loc or mat.get("dep_loc") or "1mg,10mg,100mg"
    a.zone_metric = a.zone_metric or mat.get("zone_metric") or "m60"
    if a.dep_loc_labels is None:
        a.dep_loc_labels = (
            mat.get("dep_loc_labels") if a.dep_loc == mat.get("dep_loc") else None
        ) or "||"


def _resolve_run(a: argparse.Namespace, p: argparse.ArgumentParser) -> None:
    """Cloud-height factor, cache, start time and range checks."""
    if a.church_factor is None:
        a.church_factor = CONFINEMENT[a.confinement][0]
    if a.ensemble < 1 or a.shots < 1:
        p.error("--ensemble and --shots must be at least 1")
    if a.met_cache:
        MET_CACHE["path"], MET_CACHE["data"] = a.met_cache, None
    a.start, a.display_tz = parse_time(a.time)
    a.as_of = parse_time(a.as_of)[0] if a.as_of else None
    if 3600 % a.dt:
        p.error("--dt must divide 3600")
    if not (-90 < a.lat < 90 and -180 <= a.lon <= 360):
        p.error("lat/lon out of range")
    if a.hours < 1 or a.hours > 240:
        p.error("--hours must be 1..240")


def _resolve_source(a: argparse.Namespace) -> None:
    """Explosion source term and the mass released."""
    a.explosion = None
    if a.explosive_mass:
        a.explosion = explosion_source(
            a.explosive_mass, a.specific_energy, a.church_factor, a.shots, a.confinement
        )
        a.release_duration = 0.0
        if a.release_mass is None:
            a.release_mass = a.explosive_mass * a.tracked_fraction * a.airborne_fraction
    if a.release_mass is None:
        a.release_mass = 1.0


def _three_levels(text: str, parse: Callable[[str], float]) -> list[float]:
    """Parse three comma-separated levels; ValueError unless there are exactly three."""
    values = [parse(v) for v in text.split(",")]
    if len(values) != 3:
        raise ValueError(f"need three levels, got {len(values)}")
    return values


def _resolve_levels(a: argparse.Namespace, p: argparse.ArgumentParser) -> None:
    """Numeric levels of concern for air (kg/m3) and ground (kg/m2), with names."""
    try:
        a.loc_values = _three_levels(a.loc, parse_conc)
    except (argparse.ArgumentTypeError, ValueError):
        p.error("--loc needs three masses per m3, e.g. 0.15mg,5mg,15mg")
    a.loc_names = [*a.loc_labels.split("|"), "", "", ""][:3]
    try:
        a.dep_loc_values = _three_levels(a.dep_loc, parse_areal)
    except (argparse.ArgumentTypeError, ValueError):
        p.error("--dep-loc needs three masses per area, e.g. 5ug/ft2,40ug/ft2,100ug/ft2")
    a.dep_loc_names = [*a.dep_loc_labels.split("|"), "", "", ""][:3]


def _tracked_mass(a: argparse.Namespace, p: argparse.ArgumentParser) -> float:
    """Mass of the tracked substance in the charge; release cases need an explosion."""
    if not a.explosion:
        p.error("--release-case needs --explosive-mass")
    return float(a.explosive_mass * a.tracked_fraction)


def _resolve_release_case(a: argparse.Namespace, p: argparse.ArgumentParser) -> None:
    """Apply ``--release-case`` / ``--respirable-fraction``: airborne share and size split.

    The all-fine cases set the airborne share and release all of it in respirable
    'fume' sizes. They differ only in mass released and the model is linear in it, so
    ``a.case_range`` records the lowest and highest share for the page to scale any
    value exactly. The respirable/coarse cases split the lofted mass between 'fume'
    sizes and coarse 30 and 100 um particles on soil.
    """
    a.case_range = None
    f_resp = a.respirable_fraction
    if a.release_case in (TNT_EQUIVALENT_CASE, TWENTY_PERCENT_CASE):
        tracked = _tracked_mass(a, p)
        f_resp = (
            0.2
            if a.release_case == TWENTY_PERCENT_CASE
            else min(1.0, a.explosion["tntKg"] / tracked)
        )
    if a.release_case in FINE_CASES:
        tracked = _tracked_mass(a, p)
        share = FINE_CASES[a.release_case]
        if share is None:
            share = min(1.0, a.explosion["tntKg"] / tracked)
        a.airborne_fraction = share
        a.release_mass = tracked * share
        f_resp = 1.0
        shares = [
            min(1.0, a.explosion["tntKg"] / tracked) if s is None else s
            for s in FINE_CASES.values()
        ]
        a.case_range = [min(shares), max(shares)]
    if a.release_case:
        a.release_note = f"'{a.release_case}' case: {RELEASE_CASES[a.release_case]}"
    if f_resp is not None:
        if not 0 <= f_resp <= 1:
            p.error("--respirable-fraction must be between 0 and 1")
        fine_rho = a.density
        fine = [(fine_rho * math.pi * (d * 1e-6) ** 3 / 6.0, f) for d, f in SIZE_PRESETS["fume"][1]]
        coarse = [(COARSE_DENSITY * math.pi * (d * 1e-6) ** 3 / 6.0, f) for d, f in COARSE_BINS]
        a.particle_mass = [
            *([(m_, f * f_resp) for m_, f in fine] if f_resp > 0 else []),
            *([(m_, f * (1 - f_resp)) for m_, f in coarse] if f_resp < 1 else []),
        ]
        a.rho_of = {m_: fine_rho for m_, _ in fine}
        a.rho_of.update(dict.fromkeys((m_ for m_, _ in coarse), COARSE_DENSITY))
        a.size_note = (
            f"{f_resp:.0%} respirable as 'fume' sizes at {fine_rho:g} kg/m3, "
            f"{1 - f_resp:.0%} coarse (30 and 100 um at {COARSE_DENSITY:g} kg/m3)"
        )
    a.respirable_fraction = f_resp


def _resolve_wind(a: argparse.Namespace, p: argparse.ArgumentParser) -> None:
    """``--wind SPEED@DIR`` as (speed m/s, direction deg), or None."""
    a.const_wind = None
    if a.wind:
        try:
            sp, di = a.wind.split("@")
            a.const_wind = (float(sp), float(di))
        except ValueError:
            p.error("--wind must look like 5@270")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the command line and resolve every derived setting.

    Material presets fill in what isn't given explicitly; the explosion source term,
    release mass, particle size bins, levels of concern and release case are worked
    out here, so :func:`simulate` gets a complete set of options.
    """
    p = build_parser()
    a = p.parse_args(argv)
    mat = MATERIALS.get(a.material, {})
    _resolve_material(a, mat, p)
    _resolve_sizes(a, mat)
    a.release_note = None
    _resolve_display(a, mat)
    _resolve_run(a, p)
    _resolve_source(a)
    _resolve_levels(a, p)
    _resolve_release_case(a, p)
    _resolve_wind(a, p)
    return a


#: One weather source for the run: (model name or None, description, met, elevation m).
MetRun: TypeAlias = "tuple[str | None, str, MetField, float | None]"


#: One uncertainty member: (label, per-step records, hourly summaries).
Member: TypeAlias = "tuple[str, list[Record], list[Json]]"


def _particle_bins(a: argparse.Namespace, log: TextIO) -> list[Bin]:
    """Settling velocity of each size bin, logged with its diameter."""
    bins = []
    for pm, frac in a.particle_mass:
        d, vs, re_ = particle_properties(pm, a.rho_of.get(pm, a.density))
        bins.append((pm, frac, vs))
        print(
            f"particle {pm:.3g} kg ({frac:.0%} of mass) -> d = {d * 1e6:.2f} um, "
            f"v_settle = {vs * 100:.3g} cm/s (Re {re_:.2g})",
            file=log,
        )
    if a.explosion:
        e = a.explosion
        print(
            f"explosion: {e['energyJ'] / 1e9:.2f} GJ = {e['tntKg']:.0f} kg TNT eq in "
            f"{e['shots']} shot(s), {e['confinement']}, cloud top {e['cloudTop']:.0f} m, "
            f"{a.release_mass:.4g} kg {a.tracked_name or 'material'} lofted",
            file=log,
        )
    return bins


def _try_model(a: argparse.Namespace, m: str, log: TextIO, *, use_levels: bool) -> MetRun | None:
    """Return weather from one named model, or None (logged) if it doesn't cover the run."""
    try:
        nm, mt, el = build_met(
            a.lat,
            a.lon,
            a.start,
            a.hours,
            a.wind_grid,
            None,
            use_levels,
            model=m.strip(),
            now=getattr(a, "as_of", None),
        )
    except (SystemExit, ValueError, KeyError) as e:
        print(f"weather model {m} skipped: {str(e).splitlines()[-1].strip()}", file=log)
        return None
    return (m.strip(), nm, mt, el)


def _load_weather(a: argparse.Namespace, log: TextIO) -> list[MetRun]:
    """Weather for every requested model that covers the run; the first is shown.

    Historical dates, ``--wind`` and ``best-match`` use a single source.
    """
    use_lev = not getattr(a, "no_pressure_levels", False)
    wm = getattr(a, "weather_model", "best-match") or "best-match"
    names = WEATHER_ENSEMBLE if wm == "ensemble" else [m for m in wm.split(",") if m.strip()]
    now = getattr(a, "as_of", None) or dt.datetime.now(dt.timezone.utc)
    historical = a.start + dt.timedelta(hours=a.hours) < now - dt.timedelta(days=6)
    mets: list[MetRun] = []
    if a.const_wind is None and not historical and names != ["best-match"]:
        for m in names:
            got = _try_model(a, m, log, use_levels=use_lev)
            if got:
                mets.append(got)
    if not mets:
        nm, mt, el = build_met(
            a.lat,
            a.lon,
            a.start,
            a.hours,
            a.wind_grid,
            a.const_wind,
            use_lev,
            now=getattr(a, "as_of", None),
        )
        mets = [(None, nm, mt, el)]
    if len(mets) > 1:
        print(
            "weather models: "
            + ", ".join(str(m) for m, _, _, _ in mets)
            + f" (shown: {mets[0][0]})",
            file=log,
        )
    return mets


def _ensemble_offsets(a: argparse.Namespace) -> tuple[list[float], float, int]:
    """Wind-field rotations (deg) for ``--ensemble N``, the slice width and N.

    Rotated members sit at the centers of N equal slices of +/- ``dir_spread``, so
    smearing each by half a slice leaves no gaps. 0 is always included.
    """
    n_ens = getattr(a, "ensemble", 1)
    step = 2.0 * a.dir_spread / n_ens
    offsets = [-a.dir_spread + step / 2 + k * step for k in range(n_ens)] if n_ens > 1 else [0.0]
    if not any(abs(o) < 1e-9 for o in offsets):
        offsets.append(0.0)
    return offsets, step, n_ens


def _run_members(
    a: argparse.Namespace, mets: Sequence[MetRun], bins: Sequence[Bin], offsets: Sequence[float]
) -> list[Member]:
    """Uncertainty members: every weather model at every rotation, except the shown run."""
    members: list[Member] = []
    for k, (mname, _, met_k, _) in enumerate(mets):
        if getattr(a, "rain", None) is not None:
            met_k.f["precip"] = np.full_like(met_k.f["precip"], float(a.rain))
        for off in offsets:
            if k == 0 and abs(off) < 1e-9:
                continue  # that is the run already made
            rec_m, hourly_m = run_model(
                a, rotated_met(met_k, off) if off else met_k, bins, a.lat, a.lon
            )
            label = (mname or "wind") + (f" {off:+g}°" if off else "")
            members.append((label, rec_m, hourly_m))
    return members


def _member_domain(
    records: list[Record], members: Sequence[Member], half: float
) -> list[Record] | None:
    """Return the records that set the map window: every member, each turned +/- ``half``."""
    if not members:
        return None
    domain = records + [r for _, rec_m, _ in members for r in rec_m]
    turned: list[Record] = []
    for d in (-half, half):
        c, s_ = math.cos(math.radians(d)), math.sin(math.radians(d))
        turned += [(r[0], r[1] * c + r[2] * s_, -r[1] * s_ + r[2] * c, *r[3:]) for r in domain]
    return domain + turned


def _envelope(
    a: argparse.Namespace,
    F: dict[str, FloatArray],
    members: Sequence[Member],
    grid: tuple[FloatArray, FloatArray, float | None, list[Record] | None],
    half: float,
    mets: Sequence[MetRun],
) -> Json:
    """Add ``env_*`` fields (highest value of any member, smeared) to ``F``; describe them."""
    xe, ye, extent, domain = grid
    n_ens = getattr(a, "ensemble", 1)
    env = {k: F[k].copy() for k in ("conc", "peak", "m60", "dep")}
    for _, rec_m, _ in members:
        Fm, _ = grid_fields(rec_m, a.hours, a.grid, a.dt, extent, domain, counts=False)
        for k, arr in env.items():
            np.maximum(arr, Fm[k], out=arr)
    F.update({f"env_{k}": angular_smear(v, xe, ye, half) for k, v in env.items()})
    return {
        "n": len(members) + 1,
        "spread": a.dir_spread if n_ens > 1 else half,
        "models": [m for m, _, _, _ in mets] if len(mets) > 1 else None,
        "shown": mets[0][0],
        "rotations": n_ens if n_ens > 1 else 0,
        "labels": [lb for lb, _, _ in members],
        "tracks": [[h_["centroid"] for h_ in hourly_m] for _, _, hourly_m in members],
    }


def _at_source(met: MetField, name: str, th: float, a: argparse.Namespace) -> float:
    """Field ``name`` at the release point at met hour ``th``."""
    return float(met.sample(name, np.array([th]), np.array([a.lat]), np.array([a.lon]))[0])


def _wind_from(u: float, v: float) -> int:
    """Compass direction (deg) the wind with components (u, v) blows FROM."""
    return round((math.degrees(math.atan2(-u, -v)) + 360) % 360)


def _hours_output(
    a: argparse.Namespace, met: MetField, hourly: Sequence[Json], F: dict[str, FloatArray]
) -> list[Json]:
    """Per-hour weather at the source, mass budget, puffs and field maxima for the page."""
    t_off = (a.start - met.t0).total_seconds() / 3600.0
    conc, dep = F["conc"], F["dep"]
    hours_out = []
    for h in range(a.hours):
        th = t_off + h + 0.5

        def one(name: str, th: float = th) -> float:
            return _at_source(met, name, th, a)

        cls = int(
            met.sample("stab", np.array([th]), np.array([a.lat]), np.array([a.lon]), nearest=True)[
                0
            ]
        )
        ti = int(min(max(round(th - 0.5), 0), met.nt - 1))
        hrow = hourly[h]
        hours_out.append(
            {
                "t": (a.start + dt.timedelta(hours=h + 1)).isoformat().replace("+00:00", "Z"),
                "ws": round(math.hypot(one("u"), one("v")), 2),
                "wd": _wind_from(one("u"), one("v")),
                "wsUp": round(math.hypot(one("u_up"), one("v_up")), 2),
                "wdUp": _wind_from(one("u_up"), one("v_up")),
                "stab": CLASSES[cls],
                "blh": round(one("blh")),
                "precip": round(one("precip"), 2),
                "cloud": round(one("cloud")),
                "sw": round(one("sw")),
                "wind": [
                    [
                        round(float(la), 4),
                        round(float(lo), 4),
                        round(float(met.f["u"][ti, j, i]), 2),
                        round(float(met.f["v"][ti, j, i]), 2),
                    ]
                    for j, la in enumerate(met.lat_nodes)
                    for i, lo in enumerate(met.lon_nodes)
                ],
                # forecast sky cover (%) and precipitation (mm/h) at the same points as "wind"
                "sky": [
                    [
                        round(float(met.f["cloud"][ti, j, i])),
                        round(float(met.f["precip"][ti, j, i]), 2),
                    ]
                    for j in range(len(met.lat_nodes))
                    for i in range(len(met.lon_nodes))
                ],
                **{
                    k: hrow[k]
                    for k in ("puffs", "airborne", "dry", "wet", "spray", "released", "centroid")
                },
                "cmax": float(conc[h].max()),
                "dmax": float(dep[h].max()),
                "cmaxN": float(F["conc_n"][h].max()),
                "dmaxN": float(F["dep_n"][h].max()),
                "pmax": float(F["peak"][h].max()),
                "pmaxN": float(F["peak_n"][h].max()),
                "smax": float(F["snap"][h].max()),
                "smaxN": float(F["snap_n"][h].max()),
                # wind aloft above the source: [height m above ground, speed m/s, direction]
                "prof": [
                    [
                        round(one(f"zl{k}")),
                        round(math.hypot(one(f"ul{k}"), one(f"vl{k}")), 1),
                        _wind_from(one(f"ul{k}"), one(f"vl{k}")),
                    ]
                    for k in range(met.n_lev)
                ],
            }
        )
    return hours_out


def _bins_output(a: argparse.Namespace, bins: Sequence[Bin]) -> list[Json]:
    """Each size bin's diameter, settling and deposition velocity (5 m/s wind) for display."""
    bins_out = []
    for pm, frac, vs in bins:
        rho_b = a.rho_of.get(pm, a.density)
        d, _, _ = particle_properties(pm, rho_b)
        if a.vd_extra is None:  # deposition velocity in a 5 m/s wind, for display
            vd = float(
                zhang_deposition_velocity(
                    np.array([d]),
                    np.array([vs]),
                    zhang_surface_terms(np.array([d]), rho_b),
                    np.array([5.0]),
                    a.land_use,
                )[0]
            )
        else:
            vd = vs + a.vd_extra
        bins_out.append({"mass": pm, "frac": frac, "d": d, "vs": vs, "vd": vd, "rho": rho_b})
    return bins_out


def _meta(
    a: argparse.Namespace,
    met: MetField,
    src_name: str,
    elev: float | None,
    bins_out: list[Json],
    ensemble: Json | None,
) -> Json:
    """Build the ``meta`` block of the page data: inputs, assumptions and display settings."""
    tz = a.display_tz
    offset = tz.utcoffset(a.start) if tz else None
    return {
        "title": a.title
        or (
            f"Explosion dispersal from {a.lat:.4f}, {a.lon:.4f}"
            if a.explosion
            else f"Puff dispersal from {a.lat:.4f}, {a.lon:.4f}"
        ),
        "lat": a.lat,
        "lon": a.lon,
        "start": a.start.isoformat().replace("+00:00", "Z"),
        "tzOffsetMin": int(offset.total_seconds() // 60) if offset else 0,
        "bins": bins_out,
        "density": a.density,
        "releaseMass": a.release_mass,
        "releaseDuration": a.release_duration,
        "releaseHeight": a.release_height,
        "explosion": a.explosion,
        "explosionOpts": {
            "layers": a.cloud_layers,
            "radiusFrac": a.cloud_radius_frac,
            "airborneFraction": a.airborne_fraction,
        }
        if a.explosion
        else None,
        "trackedName": a.tracked_name,
        "trackedFraction": a.tracked_fraction,
        "material": a.material,
        "sizeNote": a.size_note,
        "releaseNote": a.release_note,
        "deposition": (
            "Zhang et al. (2001) size-resolved scheme over " + a.land_use
            if a.vd_extra is None
            else f"settling plus a fixed {a.vd_extra * 100:g} cm/s"
        ),
        "nLev": met.n_lev,
        "levelNames": met.level_names,
        "ensemble": ensemble,
        "depLoc": [
            {"value": v, "label": n} for v, n in zip(a.dep_loc_values, a.dep_loc_names, strict=True)
        ],
        "hours": a.hours,
        "dt": a.dt,
        "weather": src_name,
        "elevation": elev,
        "zUp": met.z_up,
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "homeUrl": a.home_url,
        "legendNote": a.legend_note,
        "caseRange": getattr(a, "case_range", None),
        "scavenging": a.scavenging,
        "residualLayer": bool(getattr(a, "residual_layer", True)),
        "loc": [{"value": v, "label": n} for v, n in zip(a.loc_values, a.loc_names, strict=True)],
        "spray": (
            {
                "flowLpm": a.spray_flow,
                "radius": a.spray_radius,
                "height": a.spray_height,
                "dropMm": a.spray_drop,
                "startMin": a.spray_start,
                "durationMin": a.spray_duration,
                **getattr(a, "spray_info", {}),
            }
            if a.spray_flow > 0
            else None
        ),
        "scaleMax": a.scale_max,
        "scaleMin": a.scale_min,
        "decades": max(2, min(8, a.decades)),
        "units": a.units,
        "zoneMetric": a.zone_metric,
    }


def simulate(a: argparse.Namespace, log: TextIO = sys.stderr) -> Json:
    """Run the whole pipeline: weather, puff model, uncertainty members and gridding.

    Returns
    -------
    dict
        The page data: ``meta``, ``grid`` (packed fields) and ``hours``, plus
        ``_arrays`` (the unpacked fields and cell edges, not written to the page) for
        validation scripts and tests.
    """
    bins = _particle_bins(a, log)
    mets = _load_weather(a, log)
    _, src_name, met, elev = mets[0]
    if getattr(a, "rain", None) is not None:
        met.f["precip"] = np.full_like(met.f["precip"], float(a.rain))
        src_name += f"; precipitation set to {a.rain:g} mm/h"
    print(
        f"weather: {src_name}, wind grid {len(met.lat_nodes)}x{len(met.lon_nodes)}, "
        f"winds aloft at {met.z_up:.0f} m"
        + (f" and {', '.join(met.level_names)}" if met.n_lev else ""),
        file=log,
    )

    records, hourly = run_model(a, met, bins, a.lat, a.lon)
    # Uncertainty members: every other weather model, and (with --ensemble N) each model
    # with its whole wind field turned a few degrees.
    offsets, step, n_ens = _ensemble_offsets(a)
    members = _run_members(a, mets, bins, offsets)
    # half-width each member is smeared by: half a rotation slice, or the residual
    # direction error allowed around each weather model
    half = step / 2 if n_ens > 1 else (MODEL_RESIDUAL_DEG if len(mets) > 1 else 0.0)
    extent = a.extent_km * 1000 if a.extent_km else None
    domain = _member_domain(records, members, half)
    F, (xe, ye, dx) = grid_fields(records, a.hours, a.grid, a.dt, extent, domain)
    ensemble = None
    if members:
        ensemble = _envelope(a, F, members, (xe, ye, extent, domain), half, mets)
        print(
            f"uncertainty view: {len(members) + 1} runs"
            + (f" over {len(mets)} weather models" if len(mets) > 1 else "")
            + f", each smeared +/-{half:g} deg",
            file=log,
        )
    conc = F["conc"]
    print(f"grid: {conc.shape[2]}x{conc.shape[1]} cells of {dx / 1000:.3g} km", file=log)

    coslat0 = math.cos(math.radians(a.lat))
    hours_out = _hours_output(a, met, hourly, F)
    bins_out = _bins_output(a, bins)
    payload: Json = {
        "meta": _meta(a, met, src_name, elev, bins_out, ensemble),
        "grid": {
            "nx": conc.shape[2],
            "ny": conc.shape[1],
            "dx": dx,
            "north": a.lat + math.degrees(ye[0] / R_EARTH),
            "south": a.lat + math.degrees(ye[-1] / R_EARTH),
            "west": a.lon + math.degrees(xe[0] / (R_EARTH * coslat0)),
            "east": a.lon + math.degrees(xe[-1] / (R_EARTH * coslat0)),
            **{k: pack(v) for k, v in F.items()},
        },
        "hours": hours_out,
    }
    payload["meta"]["hysplit"] = hysplit_files(a, bins_out, payload["grid"])
    # raw arrays for validation scripts (not written to HTML)
    payload["_arrays"] = dict(F, xe=xe, ye=ye, dx=dx)
    return payload


def main(argv: Sequence[str] | None = None) -> str:
    """Command-line entry point; returns the path of the HTML written."""
    a = parse_args(argv)
    payload = simulate(a)
    out = a.out or (f"dispersal_{a.lat:.3f}_{a.lon:.3f}_{a.start.strftime('%Y%m%dT%H%MZ')}.html")
    size = write_html(payload, out)
    print(f"wrote {out} ({size / 1e6:.2f} MB)", file=sys.stderr)
    if a.hysplit:
        folder = Path(a.hysplit)
        folder.mkdir(parents=True, exist_ok=True)
        for name, text in payload["meta"]["hysplit"].items():
            (folder / name).write_text(text, encoding="utf-8")
        print(f"wrote HYSPLIT inputs to {a.hysplit}/", file=sys.stderr)
    return str(out)


if __name__ == "__main__":
    main()
