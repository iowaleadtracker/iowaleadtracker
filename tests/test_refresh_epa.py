"""Summarizing EPA's public layers for the map (tools/refresh_epa.py), without the network."""

from __future__ import annotations

import datetime as dt
import json

import pytest

from tools import refresh_epa as epa

UTC = dt.timezone.utc


def _ms(text: str) -> float:
    return dt.datetime.fromisoformat(text).replace(tzinfo=UTC).timestamp() * 1000


def _site(sid: str, instruments: str, lat: float = 40.7) -> dict[str, object]:
    return {
        "attributes": {"Station_ID": sid, "Instrument_Type": instruments},
        "geometry": {"x": -91.3, "y": lat},
    }


def _reading(sid: str, when: str, value: float) -> dict[str, object]:
    return {
        "Air_Station_ID": sid,
        "Mon_Date_Time": _ms(when),
        "Mon_Results": value,
        "Mon_Units": "µg/m3",
    }


SITES = [
    _site("AS-01", "Dust Trak, AreaRAE, Air Cassette, Summa Cannister"),
    _site("AS-02", "Air Cassette, Summa Cannister", 40.6),
]
READINGS = [
    _reading("AS01", "2026-11-25 14:00", 0.006),  # before the blast
    _reading("AS01", "2026-11-25 15:10", 0.002),
    _reading("AS01", "2026-11-25 16:00", 0.004),
    _reading("AS01", "2026-11-25 17:00", 0.004),  # the same highest again, later
    _reading("AS01", "2026-11-26 21:00", 0.0),
]
SOIL = [
    # two samples at one spot (EPA lists some spots more than once): one place on the map
    {
        "attributes": {"Sample_Start_Date_Time": _ms("2026-11-23 12:30")},
        "geometry": {"x": -91.2, "y": 40.8},
    },
    {
        "attributes": {"Sample_Start_Date_Time": _ms("2026-11-23 10:00")},
        "geometry": {"x": -91.2, "y": 40.8},
    },
]
NOW = dt.datetime(2026, 11, 28, 7, 12, tzinfo=UTC)


def test_sites_get_a_kind_by_what_they_can_say_about_lead() -> None:
    out = epa.summarize(SITES, READINGS, SOIL, NOW)
    by_id = {s.get("id", s["kind"]): s for s in out["sites"]}
    assert by_id["AS01"]["kind"] == "lead"  # the layers spell it AS-01 and AS01
    assert by_id["AS01"]["instruments"] == ["xact", "dusttrak", "arearae", "cassette", "summa"]
    assert by_id["AS02"]["kind"] == "filter"
    assert by_id["soil"]["start"] == "2026-11-23T10:00Z"
    assert by_id["soil"]["starts"] == ["2026-11-23T10:00Z", "2026-11-23T12:30Z"]
    assert sum(s["kind"] == "soil" for s in out["sites"]) == 1
    # one entry per instrument there: results where EPA posted some, null where it hasn't
    assert by_id["AS01"]["readings"]["xact"]["unit"] == "µg/m³"
    assert {i: r for i, r in by_id["AS01"]["readings"].items() if i != "xact"} == dict.fromkeys(
        ["dusttrak", "arearae", "cassette", "summa"]
    )
    assert by_id["AS02"]["readings"] == {"cassette": None, "summa": None}
    assert by_id["soil"]["readings"] == {"soil": None}
    assert "unit" not in out  # each summary carries its own
    assert {s["shape"] for s in out["kinds"].values()} == {
        "diamond",
        "square-dot",
        "square",
        "triangle",
        "circle",
    }
    # each kind's details describe the sample that says something about lead; its sites have it
    assert {k: v["instrument"] for k, v in out["kinds"].items()} == {
        "lead": "xact",
        "realtime": "cassette",
        "filter": "cassette",
        "soil": "soil",
        "water": "water",
    }
    for s in out["sites"]:
        assert out["kinds"][s["kind"]]["instrument"] in s["instruments"]
    assert out["retrieved"] == "2026-11-28T07:12Z"
    assert "Nov. 28, 2026, 1:12 a.m. CST" in out["note"]


def test_readings_split_at_the_blast() -> None:
    r = epa.summarize(SITES, READINGS, [], NOW)["sites"][0]["readings"]["xact"]
    # a link to EPA's viewer with its lead layer filtered to this station, as EPA spells it
    assert r["url"] == (f"{epa.VIEWER}/?data_filter={epa.XACT_SOURCE}:Air_Station_ID%3D%27AS01%27")
    assert r["posted"] == 4  # from 9 a.m. CST on
    assert r["zero"] == 1
    assert r["max"] == {"v": 0.004, "t": "2026-11-25T16:00Z"}  # the first time it got there
    assert r["maxBefore"] == {"v": 0.006, "t": "2026-11-25T14:00Z"}
    assert r["last"] == {"v": 0.0, "t": "2026-11-26T21:00Z"}


def test_surprises_in_the_layers_stop_the_refresh() -> None:
    with pytest.raises(ValueError, match="unknown instrument"):
        epa.summarize([_site("AS-03", "Gamma Meter")], [], [], NOW)
    with pytest.raises(ValueError, match="not in the site list"):
        epa.summarize(SITES, [_reading("AS09", "2026-11-25 16:00", 0.0)], [], NOW)
    with pytest.raises(ValueError, match="mixes units"):
        epa.summarize(SITES, [*READINGS, {**READINGS[1], "Mon_Units": "ng/m3"}], [], NOW)
    with pytest.raises(ValueError, match="repeats station IDs"):  # AS-01 and AS01 are one station
        epa.summarize([*SITES, _site("AS01", "Air Cassette")], READINGS, [], NOW)


def test_a_record_without_a_value_is_left_out() -> None:
    """EPA's layer may hold a record with no result; it isn't a measurement of zero."""
    blank = {**READINGS[1], "Mon_Results": None}
    r = epa.summarize(SITES, [*READINGS, blank], [], NOW)["sites"][0]["readings"]["xact"]
    assert r["posted"] == 4


def test_the_file_is_json_with_a_site_per_line() -> None:
    data = epa.summarize(SITES, READINGS, SOIL, NOW)
    text = epa.dumps(data)
    assert json.loads(text) == data
    assert text.count('\n  {"') == len(data["sites"])


def test_water_sites_are_circles_one_per_spot_and_far_points_left_out() -> None:
    """EPA's water samples: one circle per spot with every start time; none 960 mi away."""

    def sample(when: str, lat: float, lon: float) -> dict[str, object]:
        return {
            "attributes": {"Sample_Start_Date_Time": _ms(when)},
            "geometry": {"x": lon, "y": lat},
        }

    water = [
        sample("2026-11-21 16:00", 40.70, -91.40),
        sample("2026-11-21 16:15", 40.70, -91.40),  # the same spot again
        sample("2026-11-22 09:00", 34.3798, -74.9871),  # in the Atlantic, as in EPA's layer
    ]
    out = epa.summarize(SITES, READINGS, [], NOW, water)
    w = [s for s in out["sites"] if s["kind"] == "water"]
    assert len(w) == 1
    assert w[0]["starts"] == ["2026-11-21T16:00Z", "2026-11-21T16:15Z"]
    assert w[0]["readings"] == {"water": None}
    assert out["kinds"]["water"]["shape"] == "circle"
    # the circle is water's alone: no instrument in another kind's details uses it
    assert [k for k, i in out["instruments"].items() if i.get("shape") == "circle"] == ["water"]
