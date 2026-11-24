"""Open-Meteo requests: the commercial API key and the download cache."""

from __future__ import annotations

import io
import json
import urllib.parse
from typing import TYPE_CHECKING, Any

from dispersal import met

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

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
