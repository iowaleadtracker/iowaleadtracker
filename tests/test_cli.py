"""The command line: help text and option resolution (no model runs)."""

import pytest

import puff_dispersal as puff
from dispersal.source_term import RELEASE_CASES


def test_help_renders(capsys: pytest.CaptureFixture[str]) -> None:
    """--help must not crash on the '%' in the release-case descriptions."""
    with pytest.raises(SystemExit) as done:
        puff.parse_args(["--help"])
    assert done.value.code == 0
    text = capsys.readouterr().out
    assert "--release-case" in text
    assert "20% respirable" in text


def test_every_release_case_is_documented() -> None:
    help_text = puff.build_parser().format_help()
    for case in RELEASE_CASES:
        assert case in help_text


def test_site_options_resolve() -> None:
    """The site's options give the documented lead mass, cloud and case range."""
    a = puff.parse_args(
        [
            *("--lat", "40.825518", "--lon", "-91.266502"),
            *("--time", "2026-11-23T12:00-06:00", "--release-case", "permit-100"),
            *("--material", "lead-azide", "--explosive-mass", "9700lb"),
            *("--specific-energy", "1.64", "--shots", "2", "--confinement", "earth-covered"),
        ]
    )
    assert a.release_mass == pytest.approx(9700 * 0.45359237 * 207.2 / 291.24)
    assert a.case_range == [pytest.approx(0.07), pytest.approx(1.0)]
    assert a.church_factor == 0.5
    assert a.zone_metric == "dep"  # lead: EPA cleanup levels are for surfaces


@pytest.mark.parametrize(
    "argv",
    [
        ["--lat", "95", "--lon", "0"],
        ["--lat", "40", "--lon", "0", "--dt", "7"],
        ["--lat", "40", "--lon", "0", "--hours", "0"],
        ["--lat", "40", "--lon", "0", "--release-case", "permit-100"],  # needs an explosion
        ["--lat", "40", "--lon", "0", "--loc", "1mg,2mg"],
        ["--lat", "40", "--lon", "0", "--wind", "fast"],
    ],
)
def test_bad_options_are_refused(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as done:
        puff.parse_args(argv)
    assert done.value.code == 2
