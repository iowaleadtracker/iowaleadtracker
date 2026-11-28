"""The command line: help text and option resolution (no model runs)."""

import argparse
import json
from pathlib import Path

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


def test_weather_at_centers_the_weather_grid_elsewhere() -> None:
    """--weather-at lets a run reuse weather saved for a nearby release point."""
    base = ["--lat", "40.8096", "--lon", "-91.2692", "--time", "2026-11-25T09:00-06:00"]
    assert puff.weather_point(puff.parse_args(base)) == (40.8096, -91.2692)
    moved = puff.parse_args([*base, "--weather-at", "40.825518,-91.266502"])
    assert puff.weather_point(moved) == (40.825518, -91.266502)
    assert (moved.lat, moved.lon) == (40.8096, -91.2692)  # the release point is untouched
    for bad in ("40.8", "north,west", "95,-91"):
        with pytest.raises(SystemExit):
            puff.weather_point(puff.parse_args([*base, "--weather-at", bad]))


def test_reference_sites_are_checked(tmp_path: Path) -> None:
    """A file of sites needs kinds with a known shape, and sites of a listed kind."""
    good = {
        "name": "Agency sites",
        "kinds": {"lead": {"label": "Lead monitor", "shape": "diamond"}},
        "instruments": {"x": {"name": "X", "text": "Measures lead."}},
        "sites": [{"id": "A1", "kind": "lead", "lat": 40.7, "lon": -91.3, "instruments": ["x"]}],
        "unit": "µg/m³",
    }
    path = tmp_path / "sites.json"
    path.write_text(json.dumps(good), encoding="utf-8")
    ns = argparse.Namespace(reference_sites=str(path))
    out = puff._reference_sites(ns)
    assert out is not None
    assert out["name"] == "Agency sites"
    assert out["unit"] == "µg/m³"
    assert out["sites"][0]["id"] == "A1"
    site_with_none = {**good["sites"][0], "readings": {"x": None}}  # type: ignore[index]
    path.write_text(json.dumps({**good, "sites": [site_with_none]}), encoding="utf-8")
    loaded = puff._reference_sites(ns)
    assert loaded is not None
    assert loaded["sites"][0]["readings"] == {"x": None}
    path.write_text(json.dumps(good), encoding="utf-8")
    assert "instrument" not in out["kinds"]["lead"]  # optional: the site's first is described
    assert puff._reference_sites(argparse.Namespace(reference_sites=None)) is None
    site = good["sites"][0]  # type: ignore[index]
    for bad in (
        {**good, "kinds": {"lead": {"label": "L", "shape": "star"}}},  # no such shape
        {**good, "kinds": {"lead": {"label": "L", "shape": "diamond", "instrument": "y"}}},
        {**good, "sites": [{**site, "kind": "soil"}]},  # a kind that isn't listed
        {**good, "sites": [{**site, "instruments": ["y"]}]},  # an instrument not described
        {**good, "sites": [{**site, "lat": "40.7"}]},
        {**good, "instruments": {"x": {"name": "X", "shape": "star"}}},  # no such shape
        {**good, "instruments": {"x": {"name": "X", "limit": {"v": "0.18", "unit": "u"}}}},
        {**good, "instruments": {"x": {"name": "X", "limit": {"v": 0, "unit": "u"}}}},
        {**good, "sites": [{**site, "readings": {"y": None}}]},  # not an instrument there
        {**good, "sites": [{**site, "readings": {"x": 0.002}}]},  # a number, not a summary
        {**good, "sites": [{**site, "readings": [None]}]},
        {**good, "links": [{"text": "x", "url": "javascript:alert(1)"}]},
        {"name": "x"},
    ):
        path.write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(SystemExit, match="--reference-sites"):
            puff._reference_sites(ns)


def test_the_saved_epa_sites_load() -> None:
    """The site build's file of EPA sites passes the same checks."""
    root = Path(__file__).resolve().parent.parent
    path = root / "scenarios" / "iowa-aap-lead-azide" / "epa_sites.json"
    out = puff._reference_sites(argparse.Namespace(reference_sites=str(path)))
    assert out is not None
    lead = [s for s in out["sites"] if s["kind"] == "lead"]
    assert [s["id"] for s in lead] == ["AS01", "AS02", "AS03", "AS04"]
    assert all(s["readings"]["xact"]["max"]["v"] < 0.1 for s in lead)  # µg/m³, as EPA posts
    # the Army's 0.18 µg/m³ beside lead-in-air results only (Xact, air cassette)
    limits = {k: i["limit"]["v"] for k, i in out["instruments"].items() if "limit" in i}
    assert limits == {"xact": 0.18, "cassette": 0.18}
    assert out["instruments"]["xact"]["limit"]["unit"] == "µg/m³"
    for s in out["sites"]:  # every instrument has an entry; only the Xact monitors have results
        assert set(s["readings"]) == set(s["instruments"])
        assert all((r is not None) == (i == "xact") for i, r in s["readings"].items())
    assert "not model estimates" in out["note"]


def test_reference_outlines_are_checked(tmp_path: Path) -> None:
    """A file of outlines needs a name and zones of [latitude, longitude] lines."""
    good = {
        "name": "Agency map",
        "air": {"zones": [{"label": "1 or more", "lines": [[[40, -91]]]}]},
    }
    path = tmp_path / "outlines.json"
    path.write_text(json.dumps(good), encoding="utf-8")
    ns = argparse.Namespace(reference_outlines=str(path))
    out = puff._reference_outlines(ns)
    assert out is not None
    assert out["name"] == "Agency map"
    assert out["note"] == ""
    assert out["links"] == []
    assert "dep" not in out
    assert puff._reference_outlines(argparse.Namespace(reference_outlines=None)) is None
    unsafe = {**good, "links": [{"text": "map", "url": "javascript:alert(1)"}]}
    zone = {"label": "1 or more", "lines": [[[40, -91]]]}
    mark = {"label": "T", "line": [[40, -91]]}  # one point: the page draws between two
    one_point_mark = {"name": "x", "air": {"zones": [zone], "marks": [mark]}}
    text_point = {"name": "x", "air": {"zones": [{"label": "a", "lines": [[["40", "-91"]]]}]}}
    for bad in (
        {"name": "x"},
        {"name": "x", "air": {"zones": [{"label": "", "lines": []}]}},
        unsafe,  # a link that isn't https would run in the page
        one_point_mark,  # the page draws a mark between two points
        text_point,
        [good],  # a list, not one object
    ):
        path.write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(SystemExit, match="--reference-outlines"):
            puff._reference_outlines(ns)
