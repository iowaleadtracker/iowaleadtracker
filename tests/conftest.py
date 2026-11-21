"""Shared fixtures: keep tests offline, freeze the clock, run the model."""

from __future__ import annotations

import datetime as dt
import json
import types
from typing import Any

import pytest

import puff_dispersal as puff
from dispersal import met, units

from . import SCENARIO

#: Modules that read the current time (to pick forecast or archive data, and to stamp
#: downloads and pages).
CLOCK_READERS = (puff, met, units)
SAVED_FORECASTS = SCENARIO / "met_cache" / "map_met_all.json"


def _forecast_pulled() -> dt.datetime:
    """Return the latest download stamp in the saved forecasts."""
    with SAVED_FORECASTS.open(encoding="utf-8") as f:
        stamps = json.load(f)["__fetched__"]
    return max(dt.datetime.fromisoformat(v) for v in stamps.values())


#: When the saved forecasts were downloaded, read from met_cache/map_met_all.json so a
#: forecast refresh needs no edit here.
FORECAST_PULLED = _forecast_pulled()


def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail any download, and start from a fresh --met-cache state."""

    def refuse(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("tests must not use the network")

    monkeypatch.setattr("urllib.request.urlopen", refuse)
    monkeypatch.setitem(met.MET_CACHE, "path", None)
    monkeypatch.setitem(met.MET_CACHE, "data", None)


def freeze_clock(monkeypatch: pytest.MonkeyPatch, at: dt.datetime = FORECAST_PULLED) -> dt.datetime:
    """Make the model believe it is the time the saved forecasts were pulled.

    The model picks forecast or archive data by comparing the run with "now"; without
    this, runs on the saved forecasts would stop matching them a week later.
    """

    class FrozenDatetime(dt.datetime):
        @classmethod
        def now(cls, tz: dt.tzinfo | None = None) -> FrozenDatetime:
            t = at if tz is None else at.astimezone(tz)
            return cls.fromtimestamp(t.timestamp(), tz=t.tzinfo)

    fake = types.SimpleNamespace(
        datetime=FrozenDatetime,
        timezone=dt.timezone,
        timedelta=dt.timedelta,
        tzinfo=dt.tzinfo,
    )
    for module in CLOCK_READERS:
        monkeypatch.setattr(module, "dt", fake)
    return at


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test runs without network access."""
    block_network(monkeypatch)


@pytest.fixture
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> dt.datetime:
    """Return the frozen clock: the time the saved forecasts were pulled."""
    return freeze_clock(monkeypatch)


def run_puff(argv: list[str]) -> tuple[Any, dict[str, Any]]:
    """Parse options and run the whole model quietly; return (options, payload)."""
    a = puff.parse_args(argv)
    sink = types.SimpleNamespace(write=lambda _s: None, flush=lambda: None)
    return a, puff.simulate(a, log=sink)  # type: ignore[arg-type]


#: A small, fast, network-free run: 5 m/s wind from the west, neutral, 800 m mixing height.
STEADY = [
    *("--lat", "40"),
    *("--lon", "-100"),
    *("--time", "2024-06-01T12:00Z"),
    *("--wind", "5@270"),
    *("--wind-grid", "1"),
    *("--hours", "3"),
    *("--dt", "60"),
    *("--grid", "120"),
]
