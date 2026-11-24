"""The maps' finer weather grid (sky_grid.py) and the model's --sky-grid output."""

from __future__ import annotations

import datetime as dt
import json
from typing import TYPE_CHECKING, Any

import sky_grid

import puff_dispersal as puff

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def response(day: str, missing_after: int | None = None) -> list[dict[str, Any]]:
    """Return a fake Open-Meteo answer for every grid point: two days of hours from ``day``.

    Values after hour ``missing_after`` are None, as when a model's run doesn't reach them.
    """
    lats, lons = sky_grid.grid()
    t0 = dt.datetime.fromisoformat(day)
    times = [(t0 + dt.timedelta(hours=k)).strftime("%Y-%m-%dT%H:%M") for k in range(48)]
    out = []
    for k in range(len(lats) * len(lons)):
        val = [
            None if missing_after is not None and i > missing_after else float(k % 7)
            for i in range(48)
        ]
        out.append({"hourly": {"time": times, "cloud_cover": val, "precipitation": val}})
    return out


def test_grid_is_around_the_plant() -> None:
    lats, lons = sky_grid.grid()
    assert (len(lats), len(lons)) == (2 * sky_grid.N_LAT + 1, 2 * sky_grid.N_LON + 1)
    assert lats[sky_grid.N_LAT] == sky_grid.LAT
    assert lons[sky_grid.N_LON] == sky_grid.LON
    assert lats == sorted(lats)
    assert lons == sorted(lons)


def test_url_lists_points_row_by_row() -> None:
    u = sky_grid.url("ncep_hrrr_conus", ["2026-11-25", "2026-11-26"])
    assert u.startswith("https://")
    assert "models=ncep_hrrr_conus" in u
    assert "start_date=2026-11-25" in u
    assert "end_date=2026-11-27" in u  # the last day's runs end after midnight UTC
    lats, lons = sky_grid.grid()
    q = dict(p.split("=", 1) for p in u.split("?", 1)[1].split("&"))
    la, lo = (
        q["latitude"].split(","),
        q["longitude"].split(","),
    )
    assert len(la) == len(lo) == len(lats) * len(lons)
    assert (float(la[1]), float(lo[1])) == (lats[0], lons[1])  # west to east first


def test_covers_needs_every_hour_of_the_day() -> None:
    day = "2026-11-25"
    assert sky_grid.covers(response(day), day)
    # the window starts at 11:00 CST (17 UTC); a run ending at 18 UTC misses most of it
    assert not sky_grid.covers(response(day, missing_after=18), day)
    assert not sky_grid.covers(response(day), "2026-11-26")  # data ends before its window


def test_export_writes_series_in_model_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    days = ["2026-11-25"]
    hrrr, gfs = sky_grid.url("ncep_hrrr_conus", days), sky_grid.url("gfs_seamless", days)
    saved = {
        "__fetched__": {gfs: "2026-11-24T01:00:00+00:00", hrrr: "2026-11-24T02:00:00+00:00"},
        gfs: response("2026-11-25"),
        hrrr: response("2026-11-25"),
    }
    cache = tmp_path / "sky_grid.json"
    cache.write_text(json.dumps(saved), encoding="utf-8")
    monkeypatch.setattr(sky_grid, "CACHE", cache)
    out = sky_grid.export(tmp_path / "out.json")
    assert out is not None
    data = json.loads(out.read_text(encoding="utf-8"))
    assert [s["model"] for s in data["series"]] == ["ncep_hrrr_conus", "gfs_seamless"]
    s = data["series"][0]
    assert s["fetched"] == "2026-11-24T02:00:00+00:00"
    assert s["times"][0] == "2026-11-25T00:00Z"
    assert len(s["cloud"]) == 48
    assert len(s["cloud"][0]) == len(data["lats"]) * len(data["lons"])


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
