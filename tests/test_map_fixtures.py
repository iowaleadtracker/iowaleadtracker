"""The browser tests' map data (tests/frontend/fixtures) still matches what the model writes.

The fixtures are saved model output, so they can fall behind when the model starts writing
a new key the page reads. Then the browser tests would pass without ever exercising it.
Remake them with ``python3 tools/refresh_map_fixtures.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import STEADY, run_puff

FIXTURES = Path(__file__).parent / "frontend" / "fixtures"
REFRESH = "out of date: run python3 tools/refresh_map_fixtures.py"


def _load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    return data


@pytest.fixture(scope="module")
def plain_run() -> dict[str, Any]:
    """Return a small model run with no site options: the keys every map has."""
    _, payload = run_puff([*STEADY, "--grid", "40"])
    return {k: v for k, v in payload.items() if not k.startswith("_")}


def test_fixtures_have_every_key_the_model_writes(plain_run: dict[str, Any]) -> None:
    """Every key of a plain run is in one of the fixtures: top level, meta, grid, hours.

    Between them, since the archived map is made without the sky layer.
    """
    fxs = [_load("forecast"), _load("archived")]
    assert set(plain_run) <= {k for fx in fxs for k in fx}, REFRESH
    for part in ("meta", "grid"):
        assert set(plain_run[part]) <= {k for fx in fxs for k in fx[part]}, f"{part}: {REFRESH}"
    hour_keys = {k for fx in fxs for k in fx["hours"][0]}
    assert set(plain_run["hours"][0]) <= hour_keys, f"hours: {REFRESH}"


def test_fixtures_cover_the_site_features() -> None:
    """Between them, the fixtures have each optional layer the site's maps use."""
    forecast, archived = _load("forecast"), _load("archived")
    assert "skyGrid" in forecast["meta"]  # the weather layer
    assert "outlines" in forecast["meta"]  # the Army's zones
    assert forecast["meta"].get("ensemble")  # the weather-model spread
    assert archived["meta"].get("hysplit")  # the NOAA HYSPLIT overlay
