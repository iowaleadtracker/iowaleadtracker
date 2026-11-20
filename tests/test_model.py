"""End-to-end properties of the puff model (network-free runs).

These are the properties the published maps rely on: mass is conserved, the model is
linear in the mass released (the site's tooltip scales between release cases on that
basis), the plume goes where the wind blows, and the numerics agree with the
closed-form Gaussian puff (Seinfeld and Pandis 2016; Turner 1970).
"""

import math
from typing import Any

import numpy as np
import pytest

import puff_dispersal as puff
import validate_explosion
from dispersal.met import build_met, rotated_met
from dispersal.model import run_model
from dispersal.source_term import FINE_CASES

from .conftest import STEADY, run_puff

pytestmark = pytest.mark.slow


def budget(payload: dict[str, Any]) -> dict[str, Any]:
    last: dict[str, Any] = payload["hours"][-1]
    return last


@pytest.mark.parametrize(
    "extra",
    [
        [],  # dry deposition only
        ["--rain", "2"],  # plus wet removal
        ["--spray-flow", "20000", "--release-duration", "0"],  # plus the spray zone
        ["--no-residual-layer", "--rain", "1"],
    ],
)
def test_mass_is_conserved(extra: list[str]) -> None:
    """Airborne + dry + wet deposition = mass released, at every hour."""
    _, out = run_puff([*STEADY, "--particle-diameter", "1um:0.5,30um:0.5", *extra])
    for hour in out["hours"]:
        total = hour["airborne"] + hour["dry"] + hour["wet"]
        assert total == pytest.approx(hour["released"], rel=1e-9)
    assert budget(out)["dry"] > 0


def test_deposition_map_holds_the_deposited_mass() -> None:
    """The cumulative deposition field integrates to the dry + wet total."""
    _, out = run_puff([*STEADY, "--particle-diameter", "10um", "--rain", "1", "--grid", "200"])
    arrays = out["_arrays"]
    on_map = float(arrays["dep"][-1].sum() * arrays["dx"] ** 2)
    deposited = budget(out)["dry"] + budget(out)["wet"]
    assert on_map == pytest.approx(deposited, rel=0.02)


def test_linear_in_release_mass() -> None:
    """Every field scales exactly with the mass released.

    The site's tooltip turns one case's value into the range across release cases by
    this scaling (puff_dispersal sets ``caseRange`` for it).
    """
    _, full = run_puff([*STEADY, "--release-mass", "1kg", "--rain", "1"])
    _, part = run_puff([*STEADY, "--release-mass", "70g", "--rain", "1"])
    for name in ("conc", "peak", "snap", "dep"):
        a, b = full["_arrays"][name], part["_arrays"][name]
        assert np.allclose(b, 0.07 * a, rtol=1e-10, atol=0), name
    # The 60-minute mean is a running sum (add the new step, drop the oldest), which
    # leaves rounding residue of about 1e-16 of a cell's earlier peak. That residue
    # isn't proportional between runs, so compare relative to the field's maximum;
    # the map shows only the 9 decades below it.
    a, b = full["_arrays"]["m60"], part["_arrays"]["m60"]
    assert np.allclose(b, 0.07 * a, rtol=1e-10, atol=1e-12 * b.max())


def test_release_cases_differ_only_in_mass() -> None:
    """The all-fine release cases share particle sizes, so only the mass changes."""
    base = ["--lat", "40.8", "--lon", "-91.3", "--material", "lead-azide"]
    cases = {}
    for case in FINE_CASES:
        a = puff.parse_args([*base, "--explosive-mass", "9700lb", "--release-case", case])
        cases[case] = a
    sizes = {tuple(m for m, _ in a.particle_mass) for a in cases.values()}
    assert len(sizes) == 1
    low = cases["ap42-floor"]
    assert low.case_range == [pytest.approx(0.07), pytest.approx(1.0)]
    for a in cases.values():
        assert a.release_mass == pytest.approx(
            a.explosive_mass * a.tracked_fraction * a.airborne_fraction
        )


def test_plume_travels_downwind() -> None:
    """Wind FROM the west carries the cloud east, along the source latitude."""
    _, out = run_puff([*STEADY, "--particle-diameter", "1um"])
    lat, lon = out["hours"][-1]["centroid"]
    assert lon > -100.0
    assert lat == pytest.approx(40.0, abs=0.01)
    # 5 m/s near the ground and faster aloft for 3 hours: 54-110 km
    km = (lon + 100.0) * 111.195 * math.cos(math.radians(40.0))
    assert 54 < km < 110


def test_turning_the_wind_turns_the_plume() -> None:
    a = puff.parse_args([*STEADY, "--particle-diameter", "1um"])
    bins = [(a.particle_mass[0][0], 1.0, 0.0)]
    _, met, _ = build_met(a.lat, a.lon, a.start, a.hours, 1, a.const_wind)
    _, straight = run_model(a, met, bins, a.lat, a.lon)
    _, turned = run_model(a, rotated_met(met, 20.0), bins, a.lat, a.lon)

    def bearing(hour: dict) -> float:
        la, lo = hour["centroid"]
        x = (lo - a.lon) * math.cos(math.radians(a.lat))
        return math.degrees(math.atan2(x, la - a.lat))

    assert bearing(turned[-1]) - bearing(straight[-1]) == pytest.approx(20.0, abs=0.5)


def test_averages_never_exceed_the_peak() -> None:
    """Means can't top the short-term peak they average.

    The running 60-minute mean reaches back into the previous hour, so in the hour
    after a cloud passes it is bounded by the peak of that hour and the one before,
    not by the current hour's peak alone (validate_explosion check 7).
    """
    _, out = run_puff([*STEADY, "--particle-diameter", "1um", "--release-duration", "1"])
    f = out["_arrays"]
    tol = 1 + 1e-12
    assert np.all(f["conc"] <= f["peak"] * tol)
    assert np.all(f["snap"] <= f["peak"] * tol)
    prev = np.concatenate([np.zeros_like(f["peak"][:1]), f["peak"][:-1]])
    assert np.all(f["m60"] <= np.maximum(f["peak"], prev) * tol + 1e-12 * f["m60"].max())
    assert np.all(f["m60"].max(axis=0) <= f["peak"].max(axis=0) * tol + 1e-12 * f["m60"].max())


def test_matches_the_analytic_gaussian_puff() -> None:
    """validate_explosion check 2: 5-layer cloud vs the closed form, beyond 5 km."""
    worst = validate_explosion.check_analytic()
    assert worst < validate_explosion.ANALYTIC_TOL


def test_validation_script_offline_checks_pass() -> None:
    """Material preset, winds aloft, ensemble envelope, deposition and release cases."""
    assert validate_explosion.check_new_features()
