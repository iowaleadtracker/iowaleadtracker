"""Open-Meteo requests: the commercial API key and the download cache."""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.parse
from typing import TYPE_CHECKING, Any

import pytest

from dispersal import met

if TYPE_CHECKING:
    from pathlib import Path

FORECAST = "https://api.open-meteo.com/v1/forecast?latitude=41.5&longitude=-91.2"
ARCHIVE = "https://archive-api.open-meteo.com/v1/archive?latitude=41.5"


def test_free_api_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no key (or a blank one) requests go to the free API unchanged."""
    monkeypatch.delenv(met.API_KEY_ENV, raising=False)
    assert met._request_url(FORECAST) == FORECAST
    monkeypatch.setenv(met.API_KEY_ENV, "  ")
    assert met._request_url(FORECAST) == FORECAST


def test_key_switches_to_customer_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    """A key sends forecast and archive requests to the customer servers, with the key."""
    monkeypatch.setenv(met.API_KEY_ENV, "k&y")
    fc = urllib.parse.urlsplit(met._request_url(FORECAST))
    assert fc.netloc == "customer-api.open-meteo.com"
    assert fc.path == "/v1/forecast"
    assert urllib.parse.parse_qs(fc.query) == {
        "latitude": ["41.5"],
        "longitude": ["-91.2"],
        "apikey": ["k&y"],
    }
    ar = urllib.parse.urlsplit(met._request_url(ARCHIVE))
    assert ar.netloc == "customer-archive-api.open-meteo.com"
    assert urllib.parse.parse_qs(ar.query)["apikey"] == ["k&y"]


def test_key_not_sent_to_other_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    """The key is only ever added for Open-Meteo's own API hosts."""
    monkeypatch.setenv(met.API_KEY_ENV, "secret")
    other = "https://example.com/v1/forecast?x=1"
    assert met._request_url(other) == other


def test_key_never_reaches_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The cache stores responses under the free-API address, never the key.

    So the key isn't saved to a file, and saved forecasts match with or without one.
    """
    monkeypatch.setenv(met.API_KEY_ENV, "secret")
    sent: list[str] = []

    def fake_urlopen(req: Any, timeout: float) -> io.BytesIO:  # noqa: ARG001
        sent.append(req.full_url)
        return io.BytesIO(json.dumps({"ok": 1}).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    cache = tmp_path / "met.json"
    monkeypatch.setitem(met.MET_CACHE, "path", str(cache))
    assert met.http_json(FORECAST) == {"ok": 1}
    assert len(sent) == 1
    assert sent[0].startswith("https://customer-api.open-meteo.com/")
    saved = cache.read_text(encoding="utf-8")
    assert "secret" not in saved
    assert FORECAST in json.loads(saved)
    assert met.http_json(FORECAST) == {"ok": 1}  # replayed from the cache
    assert len(sent) == 1


def _http_error(url: str, code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url, code, "Bad Request", {}, io.BytesIO(b"{}"))  # type: ignore[arg-type]


def test_a_failed_request_is_replayed_as_a_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A request that failed when downloaded fails the same way with downloads off.

    So a replay takes the same fallback the download did, instead of stopping the run with
    NotSaved (which the fallbacks can't catch). A request never made still stops it.
    """

    def refuse(req: Any, timeout: float) -> io.BytesIO:  # noqa: ARG001
        raise _http_error(req.full_url, 400)

    monkeypatch.setattr("urllib.request.urlopen", refuse)
    monkeypatch.setitem(met.MET_CACHE, "path", str(tmp_path / "met.json"))
    with pytest.raises(urllib.error.HTTPError):
        met.http_json(FORECAST)
    monkeypatch.setenv(met.CACHE_ONLY_ENV, "1")
    with pytest.raises(met.SavedFailure) as e:
        met.http_json(FORECAST)
    assert e.value.code == 400
    assert isinstance(e.value, Exception)  # the fallbacks' except Exception catches it
    with pytest.raises(met.NotSaved):
        met.http_json(FORECAST + "&other=1")


def test_replay_takes_the_same_fallback_as_the_download(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Pressure levels refused (400) when downloaded: the replay drops them the same way."""
    import datetime as dt  # noqa: PLC0415

    def answer(req: Any, timeout: float) -> io.BytesIO:  # noqa: ARG001
        if "hPa" in req.full_url:
            raise _http_error(req.full_url, 400)
        return io.BytesIO(json.dumps({"hourly": {}}).encode())

    monkeypatch.setattr("urllib.request.urlopen", answer)
    monkeypatch.setattr(met, "_data_problem", lambda *_a, **_k: None)
    monkeypatch.setitem(met.MET_CACHE, "path", str(tmp_path / "met.json"))
    start = dt.datetime(2026, 11, 25, 15, tzinfo=dt.timezone.utc)
    end = start + dt.timedelta(hours=8)

    def fetch() -> tuple[str, list[Any], int | None, list[int]]:
        return met.fetch_open_meteo(
            [41.5], [-91.2], start, end, levels=[925, 850], model="gfs_seamless", now=start
        )

    downloaded = fetch()
    assert downloaded[3] == []  # fell back to no pressure levels
    monkeypatch.setattr("urllib.request.urlopen", lambda *_a, **_k: pytest.fail("downloaded"))
    monkeypatch.setenv(met.CACHE_ONLY_ENV, "1")
    assert fetch() == downloaded


@pytest.mark.parametrize(("model", "z_up"), [("ncep_hrrr_conus", 80), ("gfs_seamless", 120)])
def test_wind_level_aloft_is_one_the_model_serves(
    monkeypatch: pytest.MonkeyPatch, model: str, z_up: int
) -> None:
    """HRRR is asked for its 80 m wind (it has no 120 m); other models for 120 m."""
    import datetime as dt  # noqa: PLC0415

    asked: list[str] = []

    def answer(url: str, *_a: Any, **_k: Any) -> dict[str, Any]:
        asked.append(url)
        return {"hourly": {}}

    monkeypatch.setattr(met, "http_json", answer)
    monkeypatch.setattr(met, "_data_problem", lambda *_a, **_k: None)
    start = dt.datetime(2026, 11, 25, 15, tzinfo=dt.timezone.utc)
    got = met.fetch_open_meteo([41.5], [-91.2], start, start, model=model, now=start)
    assert got[2] == z_up
    hourly = urllib.parse.parse_qs(urllib.parse.urlsplit(asked[0]).query)["hourly"][0]
    assert f"wind_speed_{z_up}m" in hourly.split(",")


def test_low_pressure_levels_kept_on_high_pressure_days() -> None:
    """At the Iowa plant (222 m) 1000 and 975 hPa are asked for; on high ground they aren't.

    On Nov. 25, 2026 the ground pressure there was 1005 hPa, putting 975 hPa near 250 m.
    """
    assert met.pressure_levels_for(222.0) == [1000, 975, 950, 925, 900, 850, 800, 700]
    assert met.pressure_levels_for(1600.0)[0] == 850


def test_ecmwf_mixing_height_comes_from_its_9_km_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """ecmwf_ifs025 has no mixing height: it is copied in from ecmwf_ifs, hour by hour."""
    import numpy as np  # noqa: PLC0415

    times = ["2026-11-25T15:00", "2026-11-25T16:00"]
    data = [{"hourly": {"time": times, "boundary_layer_height": [None, None]}} for _ in range(2)]
    src = met._MetSource("x", data, 120, [], np.array([40.8]), np.array([-91.3, -91.2]))
    asked: list[str] = []

    def answer(url: str, *_a: Any, **_k: Any) -> list[dict[str, Any]]:
        asked.append(url)
        hourly = {"time": times[::-1], "boundary_layer_height": [550.0, 345.0]}
        return [{"hourly": hourly}, {"hourly": hourly}]

    monkeypatch.setattr(met, "http_json", answer)
    assert met._borrow_mixing_height(src, "ecmwf_ifs025") == "ecmwf_ifs"
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(asked[0]).query)
    assert q["models"] == ["ecmwf_ifs"]
    assert q["hourly"] == ["boundary_layer_height"]
    assert data[1]["hourly"]["boundary_layer_height"] == [345.0, 550.0]  # matched by time
    # a model with its own mixing height, or none to borrow from, asks for nothing
    assert met._borrow_mixing_height(src, "ecmwf_ifs025") is None
    assert met._borrow_mixing_height(src, "gfs_global") is None
    assert len(asked) == 1
