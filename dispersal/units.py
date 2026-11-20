"""Input parsing: masses, concentrations, size distributions and times."""

from __future__ import annotations

import argparse
import datetime as dt
import re
from typing import TYPE_CHECKING

from .constants import M2_PER_FT2

if TYPE_CHECKING:
    from .types import SizeDist


MASS_UNITS = {
    "kg": 1.0,
    "g": 1e-3,
    "mg": 1e-6,
    "ug": 1e-9,
    "µg": 1e-9,
    "mcg": 1e-9,
    "ng": 1e-12,
    "pg": 1e-15,
    "fg": 1e-18,
    "t": 1e3,
    "lb": 0.45359237,
    "oz": 0.028349523125,
    "gr": 6.479891e-5,
    # "t" is a metric ton (tonne); "ton" is a U.S. short ton (2,000 lb)
    "tonne": 1e3,
    "tonnes": 1e3,
    "ton": 907.18474,
    "tons": 907.18474,
}


VOLUME_UNITS = {"m3": 1.0, "cm3": 1e-6, "cc": 1e-6, "ml": 1e-6, "l": 1e-3}


AREA_UNITS = {"m2": 1.0, "ft2": M2_PER_FT2, "cm2": 1e-4}


LENGTH_UNITS = {"nm": 1e-9, "um": 1e-6, "µm": 1e-6, "μm": 1e-6, "mm": 1e-3, "m": 1.0}


_NUMBER = r"\s*([0-9.]+(?:[eE][-+]?\d+)?)\s*"


def parse_mass(text: str | float) -> float:
    """Parse a mass such as ``'25ng'``, ``'1.5 ug'``, ``'2e-11'`` or ``'3 kg'``.

    Returns kilograms. A bare number is taken as kg.
    """
    m = re.fullmatch(_NUMBER + r"([a-zA-Zµ]*)\s*", str(text))
    if not m:
        raise argparse.ArgumentTypeError(f"cannot parse mass {text!r}")
    value, unit = float(m.group(1)), m.group(2).lower() or "kg"
    if unit not in MASS_UNITS:
        raise argparse.ArgumentTypeError(
            f"unknown mass unit {unit!r}; use one of {', '.join(MASS_UNITS)}"
        )
    return value * MASS_UNITS[unit]


def parse_conc(text: str) -> float:
    """Parse a concentration such as ``'0.2ug/cm3'`` or ``'150ug/m3'``; returns kg/m3.

    Without a volume unit the mass is taken as per m3.
    """
    mass, _, vol = str(text).strip().partition("/")
    v = vol.strip().lower().replace("³", "3") or "m3"
    if v not in VOLUME_UNITS:
        raise argparse.ArgumentTypeError(f"unknown volume unit {vol!r}; use m3, cm3 or L")
    return parse_mass(mass) / VOLUME_UNITS[v]


def parse_areal(text: str) -> float:
    """Parse a mass per area such as ``'5ug/ft2'`` or ``'1mg/m2'``; returns kg/m2.

    Without an area unit the mass is taken as per m2.
    """
    mass, _, area = str(text).strip().partition("/")
    a_ = area.strip().lower().replace("²", "2") or "m2"
    if a_ not in AREA_UNITS:
        raise argparse.ArgumentTypeError(f"unknown area unit {area!r}; use m2, ft2 or cm2")
    return parse_mass(mass) / AREA_UNITS[a_]


def _normalized(bins: SizeDist, text: str, what: str) -> SizeDist:
    """Scale the fractions of a size distribution to sum to 1."""
    total = sum(f for _, f in bins)
    if not bins or total <= 0:
        raise argparse.ArgumentTypeError(f"bad particle {what} distribution {text!r}")
    return [(x, f / total) for x, f in bins]


def parse_diam_dist(text: str) -> SizeDist:
    """Parse ``'3um'`` or ``'1um:0.25,10um:0.75'`` into [(diameter m, mass fraction)].

    A bare number is in micrometres; fractions are normalized to sum to 1.
    """
    bins = []
    for part in str(text).split(","):
        if not part.strip():
            continue
        d, _, frac = part.partition(":")
        m = re.fullmatch(_NUMBER + r"([a-zA-Zµμ]*)\s*", d)
        if not m or (m.group(2) or "um") not in LENGTH_UNITS:
            raise argparse.ArgumentTypeError(f"cannot parse diameter {d!r}")
        bins.append(
            (
                float(m.group(1)) * LENGTH_UNITS[m.group(2) or "um"],
                float(frac) if frac.strip() else 1.0,
            )
        )
    return _normalized(bins, text, "diameter")


def parse_size_dist(text: str) -> SizeDist:
    """Parse ``'25ng'`` or ``'1pg:0.2,30pg:0.3,1ng:0.5'`` into [(particle mass kg, fraction)].

    Fractions are normalized to sum to 1.
    """
    bins = []
    for part in str(text).split(","):
        if not part.strip():
            continue
        mass, _, frac = part.partition(":")
        bins.append((parse_mass(mass), float(frac) if frac.strip() else 1.0))
    return _normalized(bins, text, "size")


def parse_time(text: str | None) -> tuple[dt.datetime, dt.tzinfo]:
    """Parse an ISO 8601 time; naive times are UTC.

    Returns
    -------
    tuple
        The time as an aware UTC datetime, and the time zone it was given in (for display).
        ``None``, ``''`` and ``'now'`` mean the current hour.
    """
    if text in (None, "", "now"):
        t = dt.datetime.now(dt.timezone.utc)
        return t.replace(minute=0, second=0, microsecond=0), dt.timezone.utc
    s = str(text).strip().replace(" ", "T")
    if s.endswith(("Z", "z")):
        s = s[:-1] + "+00:00"
    try:
        t = dt.datetime.fromisoformat(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"cannot parse time {text!r}") from None
    tz = t.tzinfo or dt.timezone.utc
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t.astimezone(dt.timezone.utc), tz
