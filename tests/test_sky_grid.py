"""The maps' finer weather grid (sky_grid.py) and the model's --sky-grid output."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import pytest
import sky_grid

import puff_dispersal as puff


def response(
    day: str,
    n: int,
    missing_after: int | None = None,
    n_hours: int = 48,
    missing_before: int | None = None,
) -> list[dict[str, Any]]:
    """Return a fake Open-Meteo answer for ``n`` points: ``n_hours`` hours from ``day``.

    Values after hour ``missing_after`` are None, as when a model's run doesn't reach them;
    values before hour ``missing_before`` are None, as for a run that starts late.
    """
    t0 = dt.datetime.fromisoformat(day)
    times = [(t0 + dt.timedelta(hours=k)).strftime("%Y-%m-%dT%H:%M") for k in range(n_hours)]
    out = []
    for k in range(n):
        val = [
            None
            if (missing_after is not None and i > missing_after)
            or (missing_before is not None and i < missing_before)
            else float(k % 7)
            for i in range(n_hours)
        ]
        out.append({"hourly": {"time": times, "cloud_cover": val, "precipitation": val}})
    return out


def query(u: str) -> dict[str, str]:
    return dict(p.split("=", 1) for p in u.split("?", 1)[1].split("&"))


class FakeApi:
    """Offline Open-Meteo: records the URLs asked for; can fail, and HRRR can be short."""

    def __init__(self) -> None:
        self.asked: list[str] = []
        self.hrrr_ends = 18  # hour of its first day after which HRRR has no values
        self.fail = False  # raise like an HTTP error (rate limit, bad request)

    def __call__(self, u: str) -> list[dict[str, Any]]:
        """Answer one request, as http_json would."""
        self.asked.append(u)
        if self.fail:
            raise OSError("HTTP Error 429: Too Many Requests")
        q = query(u)
        n = len(q["latitude"].split(","))
        hrrr = q["models"] == "ncep_hrrr_conus"
        days = (dt.date.fromisoformat(q["end_date"]) - dt.date.fromisoformat(q["start_date"])).days
        return response(q["start_date"], n, self.hrrr_ends if hrrr else None, 24 * (days + 1))

    def models(self) -> list[str]:
        """Return the model of each request, in order."""
        return [query(u)["models"] for u in self.asked]


@pytest.fixture
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeApi:
    """Answer requests offline, with no pauses between them."""
    fake = FakeApi()
    monkeypatch.setattr(sky_grid, "http_json", fake)
    monkeypatch.setattr(sky_grid, "CACHE", tmp_path / "sky_grid.json")
    monkeypatch.setattr(sky_grid, "PAUSE", 0.0)
    return fake


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
    # the window starts at 8:00 CST (14 UTC); a run ending at 18 UTC misses most of it
    assert not sky_grid.covers(response(day, 3, missing_after=18), day)
    assert not sky_grid.covers(response(day, 3), "2026-11-26")  # data ends before its window
    # values only from 11:00 CST (17 UTC), the old window's start, miss the morning blasts
    assert not sky_grid.covers(response(day, 3, missing_before=17), day)
    assert sky_grid.covers(response(day, 3, missing_before=14), day)


def test_window_covers_every_blast_time() -> None:
    # From the hour of the earliest blast to the latest plus the 8-hour run, for the site
    # and the staged days alike.
    import make_map_picker as site  # noqa: PLC0415
    import staged  # noqa: PLC0415

    hours = int(site.MODEL_ARGS[site.MODEL_ARGS.index("--hours") + 1])
    for times in (site.TIMES, staged.TIMES):
        first = min(dt.time.fromisoformat(t) for t in times)
        last = max(dt.time.fromisoformat(t) for t in times)
        start = dt.datetime.combine(dt.date(2026, 11, 25), sky_grid.FIRST)
        end = start + sky_grid.LAST
        assert first.replace(minute=0) >= sky_grid.FIRST
        assert dt.datetime.combine(start.date(), last) + dt.timedelta(hours=hours) <= end


def per_model() -> int:
    """Return how many requests one model's grid costs (one per point)."""
    lats, lons = sky_grid.grid()
    return len(lats) * len(lons)


def n_requests(api: FakeApi) -> int:
    return sum(len(query(u)["latitude"].split(",")) for u in api.asked)


def test_far_out_asks_only_gfs(api: FakeApi, tmp_path: Path) -> None:
    far = NOW - dt.timedelta(days=5)  # both days more than 48 hours away
    assert sky_grid.fetch(DAYS, far) == dict.fromkeys(DAYS, "gfs_seamless")
    assert set(api.models()) == {"gfs_seamless"}
    out = sky_grid.export(tmp_path / "out.json")
    assert out is not None
    data = json.loads(out.read_text(encoding="utf-8"))
    assert [s["model"] for s in data["series"]] == ["gfs_seamless"]
    assert data["fade"] == sky_grid.FADE
    s = data["series"][0]
    assert s["times"][0] == "2026-11-25T00:00Z"
    assert len(s["cloud"][0]) == len(data["lats"]) * len(data["lons"])


def test_near_asks_hrrr_then_gfs_for_what_it_misses(api: FakeApi) -> None:
    chosen = sky_grid.fetch(DAYS, NOW)  # Wednesday is within 48 hours, Thursday isn't
    hrrr = [query(u) for u in api.asked if query(u)["models"] == "ncep_hrrr_conus"]
    assert hrrr
    assert {q["start_date"] for q in hrrr} == {"2026-11-25"}  # only the near day
    assert chosen == dict.fromkeys(DAYS, "gfs_seamless")  # the fake HRRR ends too soon
    saved = sky_grid.load()
    assert saved is not None
    assert list(saved["__sets__"]) == ["gfs_seamless"]  # an unused answer isn't saved


def test_hrrr_draws_the_days_it_covers(api: FakeApi) -> None:
    api.hrrr_ends = 47  # HRRR now reaches the end of Wednesday's maps
    assert sky_grid.fetch(DAYS, NOW) == {
        "2026-11-25": "ncep_hrrr_conus",
        "2026-11-26": "gfs_seamless",
    }


def test_requests_are_spaced_out(api: FakeApi, monkeypatch: pytest.MonkeyPatch) -> None:
    pauses: list[float] = []
    monkeypatch.delenv("OPEN_METEO_API_KEY", raising=False)
    monkeypatch.setattr(sky_grid, "PAUSE", 25.0)
    monkeypatch.setattr(sky_grid.time, "sleep", pauses.append)
    sky_grid.fetch(DAYS, NOW - dt.timedelta(days=5))
    assert pauses == [25.0] * (len(api.asked) - 1)


def test_shorter_pause_with_a_commercial_key(api: FakeApi, monkeypatch: pytest.MonkeyPatch) -> None:
    pauses: list[float] = []
    monkeypatch.setenv("OPEN_METEO_API_KEY", "test-key")
    monkeypatch.setattr(sky_grid, "PAUSE", 25.0)
    monkeypatch.setattr(sky_grid.time, "sleep", pauses.append)
    sky_grid.fetch(DAYS, NOW - dt.timedelta(days=5))
    assert pauses == [sky_grid.PAUSE_WITH_KEY] * (len(api.asked) - 1)


def test_each_model_is_kept_for_its_own_time(api: FakeApi) -> None:
    api.hrrr_ends = 47
    sky_grid.fetch(DAYS, NOW)
    n = len(api.asked)
    sky_grid.fetch(DAYS, NOW + dt.timedelta(hours=3))
    assert len(api.asked) == n  # both recent: no requests
    sky_grid.fetch(DAYS, NOW + dt.timedelta(hours=6))
    assert set(api.models()[n:]) == {"ncep_hrrr_conus"}  # HRRR is 6 hours old, GFS isn't
    m = len(api.asked)
    sky_grid.fetch(DAYS, NOW + dt.timedelta(hours=12))
    assert set(api.models()[m:]) == {"ncep_hrrr_conus", "gfs_seamless"}
    k = len(api.asked)
    sky_grid.fetch(DAYS, NOW + dt.timedelta(hours=13), force=True)
    assert len(api.asked) > k


def test_a_day_of_refreshes_stays_within_budget(api: FakeApi) -> None:
    api.hrrr_ends = 47  # the worst case: both models needed all day
    for k in range(8):  # the scheduled refresh runs every 3 hours
        sky_grid.fetch(DAYS, NOW + dt.timedelta(hours=3 * k))
    assert n_requests(api) <= 6 * per_model()  # HRRR 4 times and GFS twice
    assert n_requests(api) < 5000  # Open-Meteo's free limit is about 10,000 a day


def test_past_days_are_not_downloaded(api: FakeApi) -> None:
    later = dt.datetime(2026, 11, 26, 12, tzinfo=dt.timezone.utc)  # Wednesday's maps are over
    sky_grid.fetch(DAYS, later)
    assert {query(u)["start_date"] for u in api.asked} == {"2026-11-26"}
    n = len(api.asked)
    sky_grid.fetch(DAYS, dt.datetime(2026, 11, 28, tzinfo=dt.timezone.utc))  # all over
    assert len(api.asked) == n


def test_a_failed_download_keeps_the_saved_grid(api: FakeApi) -> None:
    sky_grid.fetch(DAYS, NOW - dt.timedelta(days=5))
    before = sky_grid.CACHE.read_bytes()
    api.fail = True
    chosen = sky_grid.fetch(DAYS, NOW, force=True)  # no exception
    assert chosen == dict.fromkeys(DAYS, "gfs_seamless")
    assert sky_grid.CACHE.read_bytes() == before


def test_a_failed_first_download_writes_nothing(api: FakeApi) -> None:
    api.fail = True
    assert sky_grid.fetch(DAYS, NOW) == {}
    saved = sky_grid.load()
    assert saved is None or not saved["__days__"]


@pytest.mark.usefixtures("api")
def test_a_grid_covering_fewer_days_is_not_written(monkeypatch: pytest.MonkeyPatch) -> None:
    sky_grid.fetch(DAYS, NOW - dt.timedelta(days=5))
    before = sky_grid.CACHE.read_bytes()
    monkeypatch.setattr(sky_grid, "covers", lambda _points, day: day == DAYS[0])
    sky_grid.fetch(DAYS, NOW - dt.timedelta(days=5), force=True)
    assert sky_grid.CACHE.read_bytes() == before


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
    assert meta["fade"] == 2  # not in the file: the default, sky_grid.FADE
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


def test_sky_grid_output_keeps_point_order_and_rain(tmp_path: Path) -> None:
    # a 2 x 2 grid, every point and hour different, rain different from cloud
    times = [f"2026-11-25T{h:02d}:00Z" for h in range(17, 23)]
    cloud = [[10 * t + k for k in range(4)] for t in range(len(times))]
    rain = [[0.01 * (100 * t + k) for k in range(4)] for t in range(len(times))]
    sky = {
        "lats": [40.0, 40.35],
        "lons": [-91.0, -90.65],
        "fade": 2,
        "series": [
            {
                "model": "gfs_seamless",
                "fetched": "x",
                "times": times,
                "cloud": cloud,
                "precip": rain,
            }
        ],
    }
    f = tmp_path / "s.json"
    f.write_text(json.dumps(sky))
    meta, hours = puff._sky_grid_output(model_args(f))
    assert meta is not None
    assert (meta["lats"], meta["lons"]) == (sky["lats"], sky["lons"])
    # map hour 1 (12:15-13:15 CST) takes 19 UTC, row 2: points in the file's order
    assert hours[0]["c"] == [20, 21, 22, 23]
    assert hours[0]["p"] == [2.0, 2.01, 2.02, 2.03]
    assert hours[2]["p"] == [4.0, 4.01, 4.02, 4.03]


def test_refresh_goes_on_when_the_weather_grid_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    monkeypatch.syspath_prepend(str(Path(puff.__file__).parent / "tools"))
    refresh_forecast = importlib.import_module("refresh_forecast")  # tools/ isn't a package

    cache, sky = tmp_path / "map.json", tmp_path / "sky.json"
    cache.write_text(json.dumps({"__fetched__": {"a": "2026-11-24T00:00:00+00:00"}, "a": 1}))
    sky.write_text("old grid")
    monkeypatch.setattr(refresh_forecast, "SKY_CACHE", sky)
    monkeypatch.setattr(refresh_forecast, "SCENARIO", tmp_path)
    monkeypatch.setattr(refresh_forecast, "ROOT", tmp_path)
    steps: list[str] = []

    def run(args: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:  # noqa: ARG001
        steps.append(" ".join(args[1:]))
        if args[1] == "sky_grid.py":
            sky.write_text("half-written grid")
            raise subprocess.CalledProcessError(1, args)
        if args[1] == "build.py":  # the lead forecasts changed
            new = {"__fetched__": {"b": "2026-11-24T03:00:00+00:00"}, "b": 2}
            cache.write_text(json.dumps(new))

    monkeypatch.setattr(refresh_forecast, "run", run)
    assert refresh_forecast.refresh(cache, ["build.py"], golden=True) == 0
    assert steps == ["sky_grid.py --fetch", "build.py", "-m tests.test_regression"]
    assert sky.read_text() == "old grid"  # put back, and the refresh went on
