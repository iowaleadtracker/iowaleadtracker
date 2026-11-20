"""Input parsing and unit conversions.

Unit factors are exact definitions (NIST SP 811): 1 lb = 0.45359237 kg,
1 U.S. short ton = 2000 lb, 1 ft = 0.3048 m.
"""

import argparse
import datetime as dt
import math

import pytest

from dispersal.constants import M2_PER_FT2
from dispersal.source_term import MATERIALS
from dispersal.units import (
    MASS_UNITS,
    parse_areal,
    parse_conc,
    parse_diam_dist,
    parse_mass,
    parse_size_dist,
    parse_time,
)

LB = 0.45359237


@pytest.mark.parametrize(
    ("text", "kg"),
    [
        ("3 kg", 3.0),
        ("2e-11", 2e-11),  # a bare number is kg
        ("25ng", 25e-12),
        ("1.5 ug", 1.5e-9),
        ("1.5 µg", 1.5e-9),
        ("1lb", LB),
        ("9700lb", 9700 * LB),
        ("5t", 5000.0),  # metric ton
        ("5tonne", 5000.0),
        ("5ton", 5 * 2000 * LB),  # U.S. short ton
    ],
)
def test_parse_mass(text: str, kg: float) -> None:
    assert parse_mass(text) == pytest.approx(kg, rel=1e-12)


def test_short_ton_is_2000_pounds() -> None:
    assert MASS_UNITS["ton"] == pytest.approx(2000 * LB, rel=1e-15)


@pytest.mark.parametrize("text", ["", "kg", "5 furlongs", "1.2.3kg"])
def test_parse_mass_rejects(text: str) -> None:
    with pytest.raises((argparse.ArgumentTypeError, ValueError)):
        parse_mass(text)


def test_parse_conc_units() -> None:
    assert parse_conc("150ug/m3") == pytest.approx(150e-9)
    assert parse_conc("0.2ug/cm3") == pytest.approx(0.2e-9 / 1e-6)
    assert parse_conc("1mg/L") == pytest.approx(1e-6 / 1e-3)
    assert parse_conc("5mg") == pytest.approx(5e-6)  # per m3 by default
    with pytest.raises(argparse.ArgumentTypeError):
        parse_conc("1mg/furlong3")


def test_parse_areal_dust_lead_levels() -> None:
    """EPA's dust-lead action levels are given per square foot (40 CFR 745.227)."""
    ft2 = 0.3048**2
    assert pytest.approx(ft2, rel=1e-15) == M2_PER_FT2
    assert parse_areal("5ug/ft2") == pytest.approx(5e-9 / ft2)
    assert parse_areal("100ug/ft2") == pytest.approx(100e-9 / ft2)
    assert parse_areal("1mg") == pytest.approx(1e-6)  # per m2 by default


def test_size_distributions_are_normalized() -> None:
    bins = parse_diam_dist("1um:1,3um:3")
    assert [d for d, _ in bins] == pytest.approx([1e-6, 3e-6])
    assert [f for _, f in bins] == pytest.approx([0.25, 0.75])
    ((d_nm, frac),) = parse_diam_dist("300nm")
    assert d_nm == pytest.approx(3e-7)
    assert frac == 1.0
    masses = parse_size_dist("1pg:0.2,30pg:0.3,1ng:0.5")
    assert sum(f for _, f in masses) == pytest.approx(1.0)
    with pytest.raises(argparse.ArgumentTypeError):
        parse_diam_dist("1um:0")


def test_parse_time_keeps_display_zone() -> None:
    t, tz = parse_time("2026-11-23T12:00-06:00")
    assert t == dt.datetime(2026, 11, 23, 18, 0, tzinfo=dt.timezone.utc)
    assert tz.utcoffset(t) == dt.timedelta(hours=-6)
    naive, tz_naive = parse_time("2024-06-01 14:00")
    assert naive.tzinfo == dt.timezone.utc
    assert tz_naive == dt.timezone.utc
    assert parse_time("2024-06-01T14:00Z")[0].hour == 14
    with pytest.raises(argparse.ArgumentTypeError):
        parse_time("next Tuesday")


def test_lead_share_of_lead_azide() -> None:
    """Pb(N3)2: 207.2 / (207.2 + 6 x 14.007) by standard atomic weights."""
    share = 207.2 / (207.2 + 6 * 14.007)
    assert MATERIALS["lead-azide"]["tracked_fraction"] == pytest.approx(share, rel=1e-4)


def test_site_lead_mass_matches_code() -> None:
    """The site says 9,700 lb of lead azide holds about 6,900 lb of lead."""
    lead_lb = 9700 * MATERIALS["lead-azide"]["tracked_fraction"]
    assert round(lead_lb, -2) == 6900
    assert math.isclose(lead_lb, 6901, abs_tol=1)
