"""The maps' finer weather grid (sky_grid.py) and the model's --sky-grid output."""

from __future__ import annotations

import datetime as dt
import json
from typing import TYPE_CHECKING, Any

import pytest
import sky_grid

import puff_dispersal as puff

if TYPE_CHECKING:
    from pathlib import Path


def response(
    day: str, n: int, missing_after: int | None = None, n_hours: int = 48
) -> list[dict[str, Any]]:
    """Return a fake Open-Meteo answer for ``n`` points: ``n_hours`` hours from ``day``.

    Values after hour ``missing_after`` are None, as when a model's run doesn't reach them.
    """
    t0 = dt.datetime.fromisoformat(day)
    times = [(t0 + dt.timedelta(hours=k)).strftime("%Y-%m-%dT%H:%M") for k in range(n_hours)]
    out = []
    for k in range(n):
        val = [
            None if missing_after is not None and i > missing_after else float(k % 7)
            for i in range(n_hours)
        ]
        out.append({"hourly": {"time": times, "cloud_cover": val, "precipitation": val}})
    return out


def query(u: str) -> dict[str, str]:
    return dict(p.split("=", 1) for p in u.split("?", 1)[1].split("&"))


@pytest.fixture
def fake_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Answer requests offline; return the list of URLs asked for.

    HRRR's run ends at 18 UTC on its first day; GFS has every hour.
    """
    asked: list[str] = []

    def answer(u: str) -> list[dict[str, Any]]:
        asked.append(u)
        q = query(u)
        n = len(q["latitude"].split(","))
        hrrr = q["models"] == "ncep_hrrr_conus"
        days = (dt.date.fromisoformat(q["end_date"]) - dt.date.fromisoformat(q["start_date"])).days
        return response(q["start_date"], n, 18 if hrrr else None, 24 * (days + 1))

    monkeypatch.setattr(sky_grid, "http_json", answer)
    monkeypatch.setattr(sky_grid, "CACHE", tmp_path / "sky_grid.json")
    return asked


NOW = dt.datetime(2026, 11, 24, 6, tzinfo=dt.timezone.utc)  # Wednesday within 48 h
DAYS = ["2026-11-25", "2026-11-26"]


def test_grid_covers_the_area_and_the_fade() -> None:
    lats, lons = sky_grid.grid()
    s, n, w, e = sky_grid.AREA
    pad = sky_grid.FADE * sky_grid.SPACING
    assert lats[0] <= s - pad + 1e-9
    assert lats[-1] >= n + pad - 1e-9
    assert lons[0] <= w - pad + 1e-9
    assert lons[-1] >= e + pad - 1e-9
    # Iowa, northern Missouri and western Illinois, and the plant
    assert s <= 38.6
    assert n >= 43.5
    assert w <= -96.6
    assert e >= -89.0
    assert lats == sorted(lats)
    assert lons == sorted(lons)
    assert len(lats) * len(lons) < 800  # Open-Meteo counts every point


def test_urls_split_the_grid_into_short_requests() -> None:
    lats, lons = sky_grid.grid()
    us = sky_grid.urls("ncep_hrrr_conus", DAYS)
    assert all(u.startswith("https://") and len(u) < 4000 for u in us)
    q = query(us[0])
    assert q["models"] == "ncep_hrrr_conus"
    assert q["start_date"] == "2026-11-25"
    assert q["end_date"] == "2026-11-27"  # the last day's runs end after midnight UTC
    pts = [
        (float(a), float(b))
        for u in us
        for a, b in zip(
            query(u)["latitude"].split(","), query(u)["longitude"].split(","), strict=True
        )
    ]
    assert pts == [(la, lo) for la in lats for lo in lons]  # row by row from the south-west


def test_covers_needs_every_hour_of_the_day() -> None:
    day = "2026-11-25"
    assert sky_grid.covers(response(day, 3), day)
    # the window starts at 11:00 CST (17 UTC); a run ending at 18 UTC misses most of it
    assert not sky_grid.covers(response(day, 3, missing_after=18), day)
    assert not sky_grid.covers(response(day, 3), "2026-11-26")  # data ends before its window


def test_far_out_asks_only_gfs(fake_api: list[str], tmp_path: Path) -> None:
    far = NOW - dt.timedelta(days=5)  # both days more than 48 hours away
    assert sky_grid.fetch(DAYS, far) == dict.fromkeys(DAYS, "gfs_seamless")
    assert {query(u)["models"] for u in fake_api} == {"gfs_seamless"}
    out = sky_grid.export(tmp_path / "out.json")
    assert out is not None
    data = json.loads(out.read_text(encoding="utf-8"))
    assert [s["model"] for s in data["series"]] == ["gfs_seamless"]
    assert data["fade"] == sky_grid.FADE
    s = data["series"][0]
    assert s["times"][0] == "2026-11-25T00:00Z"
    assert len(s["cloud"][0]) == len(data["lats"]) * len(data["lons"])


def test_near_asks_hrrr_then_gfs_for_what_it_misses(fake_api: list[str]) -> None:
    chosen = sky_grid.fetch(DAYS, NOW)  # Wednesday is within 48 hours, Thursday isn't
    hrrr = [query(u) for u in fake_api if query(u)["models"] == "ncep_hrrr_conus"]
    assert hrrr
    assert {q["start_date"] for q in hrrr} == {"2026-11-25"}  # only the near day
    assert chosen == dict.fromkeys(DAYS, "gfs_seamless")  # the fake HRRR ends too soon
    saved = sky_grid.load()
    assert saved is not None
    assert list(saved["__sets__"]) == ["gfs_seamless"]  # an unused answer isn't saved


def test_a_recent_grid_is_kept(fake_api: list[str]) -> None:
    far = NOW - dt.timedelta(days=5)
    sky_grid.fetch(DAYS, far)
    saved = sky_grid.load()
    assert saved is not None
    pulled = dt.datetime.fromisoformat(min(saved["__fetched__"].values()))
    n = len(fake_api)
    sky_grid.fetch(DAYS, pulled + dt.timedelta(hours=5))
    assert len(fake_api) == n  # kept: no requests
    sky_grid.fetch(DAYS, pulled + dt.timedelta(hours=5), force=True)
    assert len(fake_api) == 2 * n
    sky_grid.fetch(DAYS, pulled + dt.timedelta(hours=10.5))
    assert len(fake_api) == 2 * n  # 5.5 hours after the forced download: kept
    sky_grid.fetch(DAYS, pulled + dt.timedelta(hours=12))
    assert len(fake_api) == 3 * n  # too old


def test_a_day_within_hrrr_reach_is_downloaded_again(fake_api: list[str]) -> None:
    sky_grid.fetch(DAYS, NOW - dt.timedelta(days=5))
    n = len(fake_api)
    sky_grid.fetch(DAYS, NOW)  # Wednesday is now within HRRR's reach
    assert len(fake_api) > n


def test_export_without_saved_grid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sky_grid, "CACHE", tmp_path / "none.json")
    assert sky_grid.export(tmp_path / "out.json") is None


def model_args(path: Path | None) -> Any:
    """Options with just what _sky_grid_output reads: a 12:15 CST start, 3 hours."""
    start = dt.datetime(2026, 11, 25, 12, 15, tzinfo=dt.timezone(dt.timedelta(hours=-6)))
    return type("A", (), {"sky_grid": path, "start": start, "hours": 3})()


def write_series(path: Path, series: list[dict[str, Any]]) -> Path:
    path.write_text(json.dumps({"lats": [40.0, 40.3], "lons": [-91.0], "series": series}))
    return path


def series(model: str, times: list[str], first: float | None = 0.0) -> dict[str, Any]:
    vals = [[first if i == 0 else float(i), float(i)] for i in range(len(times))]
    return {"model": model, "fetched": "x", "times": times, "cloud": vals, "precip": vals}


def test_sky_grid_output_takes_the_hour_after_each_middle(tmp_path: Path) -> None:
    # hours 12:15-13:15, 13:15-14:15, 14:15-15:15 CST: middles 12:45, 13:45, 14:45, so
    # the values stamped 13:00, 14:00 and 15:00 CST (19, 20 and 21 UTC)
    times = [f"2026-11-25T{h:02d}:00Z" for h in range(17, 23)]
    f = write_series(tmp_path / "s.json", [series("gfs_seamless", times)])
    meta, hours = puff._sky_grid_output(model_args(f))
    assert meta is not None
    assert meta["model"] == "gfs_seamless"
    assert [h["c"][0] for h in hours] == [2, 3, 4]  # rows 19, 20 and 21 UTC


def test_sky_grid_output_skips_series_with_gaps(tmp_path: Path) -> None:
    times = [f"2026-11-25T{h:02d}:00Z" for h in range(19, 23)]
    short = series("ncep_hrrr_conus", times[:2])  # ends before the run does
    holes = series("ncep_hrrr_conus", times, first=None)  # a missing value
    gfs = series("gfs_seamless", times)
    for bad in (short, holes):
        f = write_series(tmp_path / "s.json", [bad, gfs])
        meta, hours = puff._sky_grid_output(model_args(f))
        assert meta is not None
        assert meta["model"] == "gfs_seamless"
        assert len(hours) == 3
    f = write_series(tmp_path / "s.json", [short])
    assert puff._sky_grid_output(model_args(f)) == (None, [])
    assert puff._sky_grid_output(model_args(None)) == (None, [])
