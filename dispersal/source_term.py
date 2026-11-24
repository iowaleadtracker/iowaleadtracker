"""The release: explosion source term, material and size presets, release cases.

The cloud top follows Church (1969) as used in LLNL HotSpot; energy converts to TNT
equivalent at 4.184 MJ/kg.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .constants import KG_PER_LB, TNT_MJ_PER_KG

if TYPE_CHECKING:
    from .types import Json


# Church (1969) stabilised cloud-top height of a chemical detonation, as used in LLNL
# HotSpot (Homann and Aluzzi 2013): H_top [m] = 76 * W^(1/4), W in pounds of TNT.
CHURCH_COEFF_M = 76.0


CHURCH_EXPONENT = 0.25


# Particle-size choices, by DIAMETER (um) and mass fraction. All three are assumptions:
# nothing here is measured for a particular event, so run more than one and compare.
SIZE_PRESETS: dict[str, tuple[str, list[tuple[float, float]], float | None]] = {
    "fume": (
        "condensed metal fume, mostly respirable (assumed)",
        [(0.3, 0.3), (1.0, 0.4), (3.0, 0.2), (10.0, 0.1)],
        None,
    ),
    "mixed": (
        "even split across 1-30 um (assumed)",
        [(1.0, 0.25), (3.0, 0.25), (10.0, 0.25), (30.0, 0.25)],
        None,
    ),
    "soil-bound": (
        "carried on entrained soil dust, 10-100 um at 2650 kg/m3 (assumed)",
        [(10.0, 1 / 3), (30.0, 1 / 3), (100.0, 1 / 3)],
        2650.0,
    ),
}


# Coarse remainder for the respirable/coarse split: carried on soil and debris (assumed).
COARSE_BINS = [(30.0, 0.5), (100.0, 0.5)]


COARSE_DENSITY = 2650.0


# Documented reference cases for how much of the tracked substance is respirable.
RELEASE_CASES = {
    "upper-bound": "all of it lofted with the chosen size mix (bounding; no data behind it)",
    "tnt-equivalent": (
        "respirable mass equal to the TNT-equivalent mass of the charge, the "
        "bounding rule in DOE-HDBK-3010 for detonations in or next to solid "
        "metal; the rest coarse"
    ),
    "20-percent": (
        "20% respirable, the general upper-bound precedent quoted in DOE-HDBK-3010; the rest coarse"
    ),
    # All-fine cases: only this share of the tracked substance gets airborne, all of it in
    # respirable 'fume' sizes, and the rest stays at the site. Based on EPA AP-42 Ch. 15
    # blasting-cap tests (EO 07, 2008), where 96-98% of the airborne dust was PM-10 and
    # lead was 27-51% of it. See scenarios/iowa-aap-lead-azide/README.md.
    "ap42-floor": (
        "7% of the lead airborne, all respirable: the lowest share consistent with "
        "EPA AP-42 Ch. 15 blasting-cap tests (low case)"
    ),
    "army-26": (
        "26% of the lead airborne, all respirable: the 'Mitigated 0.26' value on the Army's "
        "Nov. 24, 2026 public advisory plume maps, read as an emission factor; the advisory "
        "doesn't define it (middle case)"
    ),
    "tnt-fine": (
        "airborne respirable mass equal to the TNT-equivalent mass, the DOE-HDBK-3010 "
        "bounding rule for detonations, all respirable (high case)"
    ),
    "permit-100": (
        "all of the lead airborne, all respirable: the emission factor of 1.00 that "
        "EPA's Nov. 13, 2026 emergency permit requires for the Army's plume modeling"
    ),
}


FINE_CASES: dict[str, float | None] = {
    "ap42-floor": 0.07,
    "army-26": 0.26,
    "tnt-fine": None,  # None = TNT-equivalent
    "permit-100": 1.00,
}


TNT_EQUIVALENT_CASE = "tnt-equivalent"


TWENTY_PERCENT_CASE = "20-percent"


# Material presets: what is tracked, how much of the material it is, and its benchmarks.
MATERIALS: dict[str, dict[str, Any]] = {
    "lead-azide": {
        "tracked_name": "lead",
        "tracked_fraction": 207.2 / 291.24,  # Pb in Pb(N3)2, standard atomic weights
        "specific_energy": 1.54,  # MJ/kg heat of explosion
        "density": 9500.0,  # lead oxide; lead metal is 11340
        "size_preset": "mixed",
        "units": "ugft2",
        "loc": "0.15ug,1.5ug,32ug",
        "loc_labels": (
            "Lead NAAQS (a 3-month average)|10 x NAAQS (the pre-2008 standard)|"
            "DOE PAC-1 for lead, 60 min (DOE PAC/TEEL database, Dec 2025)"
        ),
        "dep_loc": "5ug/ft2,40ug/ft2,100ug/ft2",
        "dep_loc_labels": (
            "EPA dust-lead action level, floors; permit line to stay indoors|"
            "EPA dust-lead action level, window sills|EPA dust-lead action level, "
            "window troughs; permit line to also wet-clean surfaces"
        ),
        # EPA's cleanup levels (40 CFR 745.227, from Jan 12, 2026) are for lead on surfaces,
        # so threat zones default to deposition for lead.
        "zone_metric": "dep",
    },
}


# Confinement: (default multiplier on the open-air Church cloud height, description).
CONFINEMENT = {
    "open": (1.0, "open-air surface burst"),
    "earth-covered": (
        0.5,
        (
            "earth-covered or bermed charge; cloud top taken as half the "
            "open-air Church height (a screening assumption, not validated)"
        ),
    ),
}


def explosion_source(
    mass_kg: float,
    specific_mj_per_kg: float,
    church_factor: float = 1.0,
    shots: int = 1,
    confinement: str = "open",
) -> Json:
    """Energy, TNT equivalent and stabilised cloud-top height of a detonation.

    The cloud top follows Church (1969), as used by LLNL HotSpot for chemical
    explosives: ``H_top [m] = 76 * W**0.25`` with ``W`` the TNT equivalent in pounds,
    on an energy basis (1 kg TNT = 4.184 MJ). With several simultaneous shots at one
    place the material is the total, but the cloud height comes from ONE shot's charge,
    since each charge lofts its own cloud.

    Parameters
    ----------
    mass_kg
        Mass of material that detonates, kg (all shots together).
    specific_mj_per_kg
        Energy released per kg of material, MJ/kg.
    church_factor
        Multiplier on the open-air Church height (e.g. 0.5 for an earth-covered charge).
    shots
        Number of equal charges fired together.
    confinement
        Key of :data:`CONFINEMENT`, recorded with its description.

    Returns
    -------
    dict
        ``mass``, ``specificEnergy``, ``energyJ``, ``tntKg``, ``cloudTop`` (m), ``shots``,
        ``churchFactor``, ``confinement`` and ``confinementNote``.

    References
    ----------
    Church (1969); Homann and Aluzzi (2013), HotSpot 3.0 user's guide.
    """
    energy_j = mass_kg * specific_mj_per_kg * 1e6
    tnt_kg = energy_j / (TNT_MJ_PER_KG * 1e6)
    shots = max(1, int(shots))
    h_top = church_factor * CHURCH_COEFF_M * (tnt_kg / shots / KG_PER_LB) ** CHURCH_EXPONENT
    return {
        "mass": mass_kg,
        "specificEnergy": specific_mj_per_kg,
        "energyJ": energy_j,
        "tntKg": tnt_kg,
        "cloudTop": h_top,
        "shots": shots,
        "churchFactor": church_factor,
        "confinement": confinement,
        "confinementNote": CONFINEMENT[confinement][1],
    }
