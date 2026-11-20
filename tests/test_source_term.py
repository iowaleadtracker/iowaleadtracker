"""Explosion source term: TNT equivalence and the Church cloud-top height.

References: Church (1969), cloud rise from high-explosives detonations; Homann and
Aluzzi (2013), HotSpot 3.0 user's guide, which uses ``H_top = 76 W^(1/4)`` (m, W in
pounds of TNT) and whose worked examples are checked in validate_explosion.py.
"""

import pytest

import puff_dispersal as puff
import validate_explosion
from dispersal.constants import TNT_MJ_PER_KG
from dispersal.source_term import explosion_source

LB = 0.45359237


def test_tnt_energy_equivalence() -> None:
    """1 kg of TNT is defined as 4.184 MJ."""
    src = explosion_source(1.0, 4.184)
    assert src["energyJ"] == pytest.approx(4.184e6)
    assert src["tntKg"] == pytest.approx(1.0)


@pytest.mark.parametrize(("tnt_lb", "published_m"), [(113, 248), (40, 191)])
def test_church_height_matches_hotspot_examples(tnt_lb: float, published_m: float) -> None:
    """HotSpot's worked examples, which report whole metres."""
    src = explosion_source(tnt_lb * LB, TNT_MJ_PER_KG)
    assert src["cloudTop"] == pytest.approx(published_m, abs=validate_explosion.HOTSPOT_TOL_M)


def test_church_formula() -> None:
    src = explosion_source(1000.0, TNT_MJ_PER_KG)
    assert src["cloudTop"] == pytest.approx(76.0 * (1000.0 / LB) ** 0.25, rel=1e-12)


def test_height_grows_as_fourth_root_of_energy() -> None:
    lo = explosion_source(5000, 1.4)["cloudTop"]
    hi = explosion_source(5000, 1.64)["cloudTop"]
    assert hi / lo == pytest.approx((1.64 / 1.4) ** 0.25, rel=1e-12)


def test_shots_share_the_material_but_each_lofts_its_own_cloud() -> None:
    one = explosion_source(4400, 1.64)
    two = explosion_source(4400, 1.64, shots=2)
    assert two["tntKg"] == pytest.approx(one["tntKg"])  # total energy unchanged
    assert two["cloudTop"] == pytest.approx(one["cloudTop"] / 2**0.25)


def test_earth_covered_halves_the_cloud() -> None:
    a = puff.parse_args(
        ["--lat", "40", "--lon", "-91", "--explosive-mass", "1t", "--confinement", "earth-covered"]
    )
    open_air = explosion_source(1000, a.specific_energy)["cloudTop"]
    assert a.explosion["cloudTop"] == pytest.approx(0.5 * open_air)


def test_iowa_cloud_top() -> None:
    """The site's case: 9,700 lb at 1.64 MJ/kg, two shots, earth-covered."""
    src = explosion_source(9700 * LB, 1.64, church_factor=0.5, shots=2)
    tnt_lb_per_shot = 9700 * 1.64 / TNT_MJ_PER_KG / 2
    assert src["cloudTop"] == pytest.approx(0.5 * 76.0 * tnt_lb_per_shot**0.25, rel=1e-12)


def test_validation_script_source_checks_pass() -> None:
    assert validate_explosion.check_source()
