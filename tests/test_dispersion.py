"""Dispersion: Briggs sigma curves, puff growth, ground reflection and stability classes.

Briggs (1973) rural curves as tabulated in Seinfeld and Pandis (2016); the Pasquill
(1961) stability table as given by Turner (1970).
"""

import math

import numpy as np
import pytest

from dispersal.constants import CLASSES
from dispersal.dispersion import (
    DAY_TABLE,
    NIGHT_TABLE,
    SY_C,
    SY_E,
    SY_K,
    SZ_C,
    SZ_E,
    SZ_K,
    WELL_MIXED_SIGMA_Z,
    briggs,
    ground_factor,
    grow_sigma,
    stability_class,
)

# Briggs (1973), open-country (rural) conditions, x in metres:
#   sigma_y = a x (1 + 0.0001 x)^-1/2 for every class
#   sigma_z: A 0.20x, B 0.12x, C 0.08x(1+0.0002x)^-1/2, D 0.06x(1+0.0015x)^-1/2,
#            E 0.03x(1+0.0003x)^-1, F 0.016x(1+0.0003x)^-1
BRIGGS_SIGMA_Y = {"A": 0.22, "B": 0.16, "C": 0.11, "D": 0.08, "E": 0.06, "F": 0.04}
BRIGGS_SIGMA_Z = {
    "A": (0.20, 0.0, 0.0),
    "B": (0.12, 0.0, 0.0),
    "C": (0.08, 2e-4, -0.5),
    "D": (0.06, 1.5e-3, -0.5),
    "E": (0.03, 3e-4, -1.0),
    "F": (0.016, 3e-4, -1.0),
}


@pytest.mark.parametrize("k", range(6))
def test_briggs_coefficients_as_published(k: int) -> None:
    cls = CLASSES[k]
    assert (SY_C[k], SY_K[k], SY_E[k]) == (BRIGGS_SIGMA_Y[cls], 1e-4, -0.5)
    assert (SZ_C[k], SZ_K[k], SZ_E[k]) == BRIGGS_SIGMA_Z[cls]


def test_briggs_neutral_one_kilometre() -> None:
    """Class D at 1 km: sigma_y = 80/sqrt(1.1) m, sigma_z = 60/sqrt(2.5) m."""
    d = 3
    assert briggs(SY_C[d], SY_K[d], SY_E[d], 1000.0) == pytest.approx(80 / math.sqrt(1.1))
    assert briggs(SZ_C[d], SZ_K[d], SZ_E[d], 1000.0) == pytest.approx(60 / math.sqrt(2.5))


def test_unstable_spreads_faster_than_stable() -> None:
    x = 5000.0
    sy = [briggs(SY_C[k], SY_K[k], SY_E[k], x) for k in range(6)]
    sz = [briggs(SZ_C[k], SZ_K[k], SZ_E[k], x) for k in range(6)]
    assert sy == sorted(sy, reverse=True)
    assert sz == sorted(sz, reverse=True)


@pytest.mark.parametrize("k", range(6))
def test_virtual_distance_growth_follows_the_curve(k: int) -> None:
    """Growing a puff from sigma(x1) by ds gives sigma(x1 + ds) in a steady class."""
    cls = np.array([k])
    for c, kk, e, sig_name in (
        (SY_C, SY_K, SY_E, "y"),
        (SZ_C, SZ_K, SZ_E, "z"),
    ):
        start = briggs(c[k], kk[k], e[k], np.array([1000.0]))
        grown = grow_sigma(start, cls, np.array([500.0]), c, kk, e)
        assert grown[0] == pytest.approx(briggs(c[k], kk[k], e[k], 1500.0), rel=1e-9), sig_name


def test_sigma_never_shrinks_when_air_stabilizes() -> None:
    """A wide unstable puff entering class F keeps its size."""
    wide = np.array([400.0])
    grown = grow_sigma(wide, np.array([5]), np.array([10.0]), SZ_C, SZ_K, SZ_E)
    assert grown[0] >= wide[0]


def test_ground_factor_no_lid() -> None:
    """At the ground, a reflected Gaussian is doubled: 2 exp(-h^2/2s^2) / (sqrt(2 pi) s)."""
    h, sz = np.array([0.0, 50.0]), np.array([30.0, 30.0])
    g = ground_factor(h, sz, np.full(2, np.inf))
    expected = 2 * np.exp(-0.5 * (h / sz) ** 2) / (math.sqrt(2 * math.pi) * sz)
    assert g == pytest.approx(expected, rel=1e-12)


def test_ground_factor_well_mixed_limit() -> None:
    """Once sigma_z > 1.6 lid, the puff is uniform through the layer: 1 / lid."""
    lid = np.array([800.0])
    g = ground_factor(np.array([100.0]), np.array([1.7 * 800.0]), lid)
    assert g[0] == pytest.approx(1 / 800.0, rel=1e-12)


def test_ground_factor_has_no_jump_at_the_well_mixed_switch() -> None:
    """Just below the switch, the image sum already gives nearly 1 / lid."""
    lid = 800.0
    just_below = ground_factor(
        np.array([100.0]), np.array([WELL_MIXED_SIGMA_Z * lid * 0.999]), np.array([lid])
    )
    assert just_below[0] == pytest.approx(1 / lid, rel=0.02)


# Pasquill (1961) as tabulated by Turner (1970): rows are 10 m wind < 2, 2-3, 3-5, 5-6, > 6 m/s;
# day columns strong / moderate / slight insolation; night columns >= 4/8 low cloud / <= 3/8.
TURNER_DAY: list[list[str]] = [
    ["A", "A-B", "B"],
    ["A-B", "B", "C"],
    ["B", "B-C", "C"],
    ["C", "C-D", "D"],
    ["C", "D", "D"],
]
TURNER_NIGHT: list[list[str | None]] = [
    [None, None],  # the table gives no class below 2 m/s at night
    ["E", "F"],
    ["D", "E"],
    ["D", "D"],
    ["D", "D"],
]


def resolve(entry: str) -> int:
    """Resolve a Turner entry the way the model does: half classes to the more unstable."""
    return CLASSES.index(entry.split("-", maxsplit=1)[0])


def test_day_table_matches_turner() -> None:
    expected = [[resolve(e) for e in row] for row in TURNER_DAY]
    assert DAY_TABLE.tolist() == expected


def test_night_table_matches_turner() -> None:
    for row, model in zip(TURNER_NIGHT, NIGHT_TABLE.tolist(), strict=True):
        if row[0] is None:  # below 2 m/s the model uses the 2-3 m/s row
            assert model == [resolve("E"), resolve("F")]
        else:
            assert model == [resolve(str(e)) for e in row]


@pytest.mark.parametrize(
    ("u", "sw", "cloud", "cls"),
    [
        (1.5, 700.0, 10.0, "A"),  # light wind, strong sun
        (4.0, 400.0, 10.0, "B"),  # moderate wind, moderate sun (B-C -> B)
        (7.0, 200.0, 10.0, "D"),  # strong wind, slight sun
        (2.5, 0.0, 20.0, "F"),  # clear night, light wind
        (2.5, 0.0, 70.0, "E"),  # cloudy night, light wind
        (7.0, 0.0, 20.0, "D"),  # windy night
        (1.5, 700.0, 95.0, "D"),  # overcast is neutral by day
        (2.5, 0.0, 95.0, "D"),  # and by night
    ],
)
def test_stability_class(u: float, sw: float, cloud: float, cls: str) -> None:
    got = stability_class(np.array([u]), np.array([sw]), np.array([cloud]))
    assert CLASSES[int(got[0])] == cls
