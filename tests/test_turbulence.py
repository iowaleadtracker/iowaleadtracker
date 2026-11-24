"""The turbulence-based spread (``--spread turbulence``, :mod:`dispersal.turbulence`).

Checks of the published formulas (exact where the formula gives a closed form, otherwise
signs and orderings), model-level properties, and the scheme's crosswind spread against
measured tracer data (Prairie Grass, Barad 1958; Project Sagebrush Phase 1, Finn et al.
2016) from ``tests/data/tracer/``. The tracer tolerances are this repository's acceptance
bands around the results documented in TURBULENCE.md, not published values. The
surface-layer scaling (:func:`scaling`) is not checked against measurements: the tracer
checks use each test's measured u*, L and w*.
"""

import math

import numpy as np
import pytest

import puff_dispersal as puff
from dispersal.turbulence import (
    SIGMA_V_MIN_DEFAULT,
    SIGMA_W_MIN,
    SYTDEP,
    averaging_factor,
    draxler_fy,
    draxler_fz,
    grow,
    scaling,
    sigma_vw,
    spread_weather,
)
from tools import tracer_sigma_y as tracer

from .conftest import STEADY, run_puff


def test_draxler_functions_as_published() -> None:
    """f_y = 1/(1 + 0.9 (t/1000)^0.5); f_z stable = 1/(1 + 0.945 (t/100)^0.806).

    Scire, Strimaitis and Yamartino (2000), Eqs. 2-65 and 2-67.
    """
    assert draxler_fy(0.0) == pytest.approx(1.0)
    assert draxler_fy(1000.0) == pytest.approx(1 / 1.9)
    assert draxler_fz(np.array([100.0]), np.array([True]))[0] == pytest.approx(1 / 1.945)
    assert draxler_fz(np.array([500.0]), np.array([False]))[0] == pytest.approx(1 / 1.9)


def test_averaging_factor() -> None:
    """(averaging / 60 min)^0.2 (Scire et al. 2000, Eq. 2-72): 1 at 60 min, 0.70 at 10."""
    assert averaging_factor(60.0) == pytest.approx(1.0)
    assert averaging_factor(10.0) == pytest.approx((1 / 6) ** 0.2)


def test_day_is_unstable_and_night_is_stable() -> None:
    """Sunny noon: L < 0 and w* > 0. Clear calm night: L > 0, w* = 0, small u*."""
    us, ell, ws = scaling(
        np.array([5.0, 2.0]), np.array([500.0, 0.0]), np.array([0.0, 0.0]), 800.0, 0.02
    )
    assert ell[0] < 0 < ell[1]
    assert ws[0] > 0.5
    assert ws[1] == 0.0
    assert us[1] < us[0]


def test_stable_friction_velocity_at_the_critical_wind() -> None:
    """At u = u_cr the stable quadratic's root vanishes: u* = C_D u_cr / 2.

    Below u_cr, u* scales with u / u_cr (EPA 2026, Eqs. 12-15).
    """
    t, z0, th = 280.0, 0.02, 0.09  # clear night: theta* = 0.09
    cd = 0.4 / math.log(10.0 / z0)
    u_cr = math.sqrt(4 * 5.0 * 10.0 * 9.81 * th / (t * cd))
    us, _, _ = scaling(np.array([u_cr, u_cr / 2]), 0.0, 0.0, 100.0, z0, t)
    assert us[0] == pytest.approx(cd * u_cr / 2, rel=1e-6)
    assert us[1] == pytest.approx(cd * u_cr / 4, rel=1e-6)


def test_night_heat_loss_is_capped() -> None:
    """theta* u* <= 0.05 m/s K (EPA 2026, Eq. 21): L = T u*^2 / (k g theta*) with the cap."""
    t = 280.0
    us, ell, _ = scaling(np.array([12.0]), 0.0, 0.0, 300.0, 0.02, t)
    theta_capped = 0.05 / us[0]
    assert 0.09 * us[0] > 0.05  # the cap is active
    assert ell[0] == pytest.approx(t * us[0] ** 2 / (0.4 * 9.81 * theta_capped), rel=1e-9)


def test_scalar_and_array_inputs_mix() -> None:
    """A scalar wind with an array temperature broadcasts instead of failing."""
    us, ell, _ = scaling(5.0, 300.0, 0.0, 800.0, 0.02, np.array([270.0, 290.0]))
    assert us.shape == ell.shape == (2,)


def test_entrainment_layer_is_continuous() -> None:
    """sigma_w is continuous at 0.8 h and h (CALPUFF Eqs. 2-56, 2-58 to 2-61)."""
    h = 800.0
    z = np.array([0.8 * h - 1e-6, 0.8 * h + 1e-6, h - 1e-6, h + 1e-6, 1.1 * h])
    n = len(z)
    _, sw = sigma_vw(
        np.full(n, 0.3), np.full(n, -50.0), np.full(n, 1.5), z, np.full(n, h), np.full(n, 1)
    )
    assert sw[0] == pytest.approx(sw[1], rel=1e-5)
    assert sw[2] == pytest.approx(sw[3], rel=1e-5)
    assert sw[4] > SIGMA_W_MIN[1]  # still turbulent in the entrainment layer above h


def test_wind_makes_the_day_more_neutral() -> None:
    """At the same sunshine, more wind gives a larger |L| (closer to neutral)."""
    _, ell, _ = scaling(np.array([2.0, 10.0]), np.array([400.0, 400.0]), 0.0, 800.0, 0.02)
    assert abs(ell[1]) > abs(ell[0])


def test_turbulence_minimums() -> None:
    """sigma_v never below its minimum; above the mixing height both fall to the minimums."""
    us, ell, ws = np.array([0.01, 0.4]), np.array([5.0, -50.0]), np.array([0.0, 1.0])
    sv, sw = sigma_vw(
        us, ell, ws, np.array([10.0, 2000.0]), np.array([50.0, 800.0]), np.array([5, 2])
    )
    assert sv[0] == pytest.approx(SIGMA_V_MIN_DEFAULT)
    assert sv[1] == pytest.approx(SIGMA_V_MIN_DEFAULT)  # above the mixing height
    assert sw[1] == pytest.approx(SIGMA_W_MIN[2])


def test_convection_adds_crosswind_turbulence() -> None:
    """sigma_v^2 = 4 u*^2 exp(-1.8 z/h) + 0.35 w*^2 (Scire et al. 2000, Eq. 2-52)."""
    sv, _ = sigma_vw(
        np.array([0.3]),
        np.array([-30.0]),
        np.array([1.5]),
        np.array([0.0]),
        np.array([800.0]),
        np.array([1]),
    )
    z = 1.0  # heights below 1 m are taken as 1 m
    want = math.sqrt(4 * 0.3**2 * math.exp(-1.8 * z / 800) + 0.35 * 1.5**2)
    assert sv[0] == pytest.approx(want, rel=1e-9)


def test_growth_never_shrinks_and_is_linear_beyond_the_switch() -> None:
    """Puffs never shrink; beyond 550 m sigma_y grows by sigma_v x factor x dt per step."""
    sy = np.array([10.0, 2000.0])
    sz = np.array([10.0, 200.0])
    sv, sw = np.array([0.8, 0.8]), np.array([0.5, 0.5])
    sy2, sz2 = grow(sy, sz, sv, sw, np.array([False, False]), 60.0, 60.0)
    assert np.all(sy2 >= sy)
    assert np.all(sz2 >= sz)
    assert sy[1] > SYTDEP
    assert sy2[1] - sy[1] == pytest.approx(0.8 * 60.0)


def test_ten_minute_basis_is_narrower() -> None:
    """The default 10-minute basis grows the cloud more slowly than the 1-hour one."""
    args = (np.array([1.0]), np.array([1.0]), np.array([1.0]), np.array([0.5]))
    a10, _ = grow(*args, np.array([False]), 300.0, 10.0)
    a60, _ = grow(*args, np.array([False]), 300.0, 60.0)
    assert a10[0] < a60[0]


def test_only_turbulence_asks_for_temperature() -> None:
    """Briggs runs keep their weather requests (and cached forecasts) unchanged."""
    assert spread_weather(puff.parse_args(["--lat", "40", "--lon", "0"])) == ()
    turb = puff.parse_args(["--lat", "40", "--lon", "0", "--spread", "turbulence"])
    assert spread_weather(turb) == ("temperature_2m",)
    fixed = puff.parse_args(
        ["--lat", "40", "--lon", "0", "--spread", "turbulence", "--air-temperature-c", "5"]
    )
    assert spread_weather(fixed) == ()


@pytest.mark.parametrize(
    "extra",
    [
        ["--spread", "turbulence", "--sigma-v-min", "-1"],
        ["--spread", "turbulence", "--sigma-v-min", "nan"],
        ["--spread", "turbulence", "--spread-averaging", "0"],
        ["--spread", "turbulence", "--spread-averaging", "90"],
        ["--spread", "fast"],
        ["--sigma-v-min", "0.5"],  # tuning options need --spread turbulence
    ],
)
def test_bad_spread_options_are_refused(extra: list[str]) -> None:
    with pytest.raises(SystemExit) as done:
        puff.parse_args(["--lat", "40", "--lon", "0", *extra])
    assert done.value.code == 2


@pytest.mark.slow
def test_mass_is_conserved_with_turbulence() -> None:
    """Airborne + dry + wet = released, as with the Briggs curves."""
    _, out = run_puff([*STEADY, "--spread", "turbulence", "--rain", "1"])
    for hour in out["hours"]:
        total = hour["airborne"] + hour["dry"] + hour["wet"]
        assert total == pytest.approx(hour["released"], rel=1e-9)
    assert "turbulence-based spread" in out["meta"]["spread"]


@pytest.mark.slow
def test_briggs_runs_carry_no_spread_note() -> None:
    """Default runs keep the original payload (no ``spread`` key)."""
    _, out = run_puff(STEADY)
    assert "spread" not in out["meta"]


@pytest.mark.slow
def test_sagebrush_sigma_y() -> None:
    """Sagebrush Phase 1 (169 values): default scheme 0.65-0.95x measured, >= 85% within 2x.

    The documented result is 0.78x and 93% (the 10-minute default is deliberately narrow;
    the 60-minute basis gives 1.13x); the original Briggs curves give 0.55x and 60%
    (Finn et al. 2016 report the curves about 2x too narrow).
    """
    cases = tracer.load_sagebrush()
    obs = [c.sigma_y for c in cases]
    gm, fac2 = tracer.score(tracer.sigma_y_turbulence(cases), obs)
    assert 0.65 < gm < 0.95
    assert fac2 >= 0.85
    gm_b, _ = tracer.score([tracer.sigma_y_briggs(c) for c in cases], obs)
    assert abs(math.log(gm)) < abs(math.log(gm_b))


@pytest.mark.slow
def test_prairie_grass_sigma_y() -> None:
    """Prairie Grass (280 values): default scheme 0.65-0.95x measured, >= 80% within 2x.

    The documented result is 0.77x and 87% with the wind moved to 10 m; the 60-minute
    basis gives 1.07x.
    """
    cases = tracer.load_prairie_grass()
    obs = [c.sigma_y for c in cases]
    gm, fac2 = tracer.score(tracer.sigma_y_turbulence(cases), obs)
    assert 0.65 < gm < 0.95
    assert fac2 >= 0.80
    gm60, _ = tracer.score(tracer.sigma_y_turbulence(cases, averaging_min=60.0), obs)
    assert 0.9 < gm60 < 1.25
