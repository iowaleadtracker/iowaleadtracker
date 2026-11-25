#!/usr/bin/env python3
"""Forecast cloud cover and precipitation on a finer grid, for the maps' weather layer.

Display only: the lead model keeps its own 5x5 weather grid (met_cache/map_met_all.json),
whose points are about 90 miles apart, so nothing here changes the lead results. This
grid has points SPACING degrees apart (about 24 miles) over Iowa, northern Missouri and
western Illinois (AREA: every map's area too), from one model per day: HRRR (NOAA, 3 km,
run every hour) when its run covers the day's maps, else GFS (NOAA's global model). HRRR
reaches 18 to 48 hours ahead, depending on the run, so it is only asked for days whose
maps end within HRRR_HOURS; further out GFS draws the layer.

    python3 sky_grid.py --fetch [--force]   # download into met_cache/sky_grid.json
    python3 sky_grid.py                     # say what is saved

--fetch only asks for days not yet over, and reuses each model's saved grid while it is
younger than MAX_AGE (HRRR 6 hours, GFS 12); --force downloads anyway. It never fails
the caller over a download problem: a failed download keeps the saved grid, and a new
grid that covers fewer days than the saved one is not written. The site build only reads
the saved file (export()); it never downloads. A forecast refresh
(tools/refresh_forecast.py) runs --fetch with the lead model's forecasts.

Open-Meteo counts each point as a request: a download costs about 770 per model. With the
3-hourly refresh that is at most about 4,600 a day while both models are needed (HRRR 4
times, GFS twice), against a free limit of about 10,000 a day that the lead forecasts
also use (README "Open-Meteo limits"). Requests are PAUSE seconds apart, for the
per-minute limit (PAUSE_WITH_KEY with a commercial key in OPEN_METEO_API_KEY).
"""

from __future__ import annotations

import datetime as dt
import json
import math
import os
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))  # the repo root, for dispersal.met

from dispersal.met import API_KEY_ENV, http_json  # noqa: E402

CACHE = HERE / "met_cache" / "sky_grid.json"
EXPORT = HERE / "outputs" / "sky_grid.json"
URL = "https://api.open-meteo.com/v1/forecast"
#: Shown at full strength: Iowa, northern Missouri and western Illinois, and every map's
#: area (south, north, west, east, degrees).
AREA = (37.0, 43.5, -96.7, -87.5)
SPACING = 0.35  # degrees between points (about 24 miles north-south)
#: Points past AREA on each side, over which the map fades the layer out.
FADE = 2
ROWS_PER_REQUEST = 6  # rows of points per request, to keep each web address short
#: Tried in this order; the first that covers a map's whole run is shown on it.
MODELS = ("ncep_hrrr_conus", "gfs_seamless")
HRRR_HOURS = 48  # HRRR is asked only for days whose maps end within this many hours
#: How long a model's saved grid is reused before it is downloaded again. GFS runs every
#: 6 hours and HRRR every hour, but each download costs about 770 requests (see above).
MAX_AGE = {"ncep_hrrr_conus": dt.timedelta(hours=6), "gfs_seamless": dt.timedelta(hours=12)}
PAUSE = 25.0  # seconds between requests: Open-Meteo also limits requests per minute
#: The pause with a commercial key (OPEN_METEO_API_KEY), whose per-minute limit is higher.
PAUSE_WITH_KEY = 2.0
VARS = ("cloud_cover", "precipitation")
#: The hours every map can need, in Central standard time: from the hour of the earliest
#: blast (8:30, so 8:00) to 22:00, past the latest (9:30; noon on the staged Wednesday) plus
#: the 8-hour run. The end is
#: where it was for the old 11:00-13:00 blasts, so when HRRR is used (hrrr_days) and the
#: daily request budget stay the same. Must cover make_map_picker.TIMES and staged.TIMES
#: (tests/test_sky_grid.py checks).
FIRST, LAST = dt.time(8), dt.timedelta(hours=14)
CST = dt.timezone(dt.timedelta(hours=-6))


def grid() -> tuple[list[float], list[float]]:
    """Return the grid's latitudes and longitudes, south to north and west to east."""
    s, n, w, e = AREA
    pad = FADE * SPACING
    n_lat = math.ceil((n - s + 2 * pad) / SPACING - 1e-9) + 1
    n_lon = math.ceil((e - w + 2 * pad) / SPACING - 1e-9) + 1
    lats = [round(s - pad + SPACING * k, 2) for k in range(n_lat)]
    lons = [round(w - pad + SPACING * k, 2) for k in range(n_lon)]
    return lats, lons


def urls(model: str, days: list[str]) -> list[str]:
    """Open-Meteo requests for every grid point, a few rows each, south to north."""
    lats, lons = grid()
    last = dt.date.fromisoformat(max(days)) + dt.timedelta(days=1)  # runs end after midnight
    out = []
    for r in range(0, len(lats), ROWS_PER_REQUEST):
        rows = lats[r : r + ROWS_PER_REQUEST]
        params = {
            "latitude": ",".join(f"{la:.2f}" for la in rows for _ in lons),
            "longitude": ",".join(f"{lo:.2f}" for _ in rows for lo in lons),
            "hourly": ",".join(VARS),
            "models": model,
            "timezone": "GMT",
            "start_date": min(days),
            "end_date": last.isoformat(),
        }
        out.append(URL + "?" + urllib.parse.urlencode(params, safe=","))
    return out


def window(day: str) -> tuple[dt.datetime, dt.datetime]:
    """Return the UTC hours a day's maps can need (see FIRST and LAST)."""
    start = dt.datetime.combine(dt.date.fromisoformat(day), FIRST, CST)
    return start.astimezone(dt.timezone.utc), (start + LAST).astimezone(dt.timezone.utc)


def covers(points: list[dict[str, Any]], day: str) -> bool:
    """Return True if a response has every point's values for all of a day's hours."""
    t0, t1 = window(day)
    times = [
        dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc)
        for s in points[0]["hourly"]["time"]
    ]
    keep = [i for i, t in enumerate(times) if t0 <= t <= t1]
    if len(keep) < (t1 - t0) // dt.timedelta(hours=1) + 1:
        return False
    return all(p["hourly"][v][i] is not None for p in points for v in VARS for i in keep)


def live_days(days: list[str], now: dt.datetime) -> list[str]:
    """Return the days whose maps haven't all ended by ``now``."""
    return [d for d in days if window(d)[1] >= now]


def hrrr_days(days: list[str], now: dt.datetime) -> list[str]:
    """Return the days, not yet over, whose maps end within HRRR_HOURS of ``now``."""
    soon = now + dt.timedelta(hours=HRRR_HOURS)
    return [d for d in live_days(days, now) if window(d)[1] <= soon]


def load() -> dict[str, Any] | None:
    """Return the saved grid file if it is for the current grid, else None."""
    if not CACHE.exists():
        return None
    saved = json.loads(CACHE.read_text(encoding="utf-8"))
    lats, lons = grid()
    return saved if saved.get("__grid__") == {"lats": lats, "lons": lons, "fade": FADE} else None


def saved_set(saved: dict[str, Any] | None, model: str) -> list[tuple[str, Any]] | None:
    """Return a model's saved requests and answers, or None."""
    parts = (saved or {}).get("__sets__", {}).get(model)
    return [(u, saved[u]) for u in parts] if parts and saved else None


def pause() -> float:
    """Return the seconds between requests: shorter with a commercial key."""
    return PAUSE_WITH_KEY if os.environ.get(API_KEY_ENV, "").strip() else PAUSE


def download(model: str, todo: list[str]) -> list[tuple[str, Any]] | None:
    """Download a model's grid for ``todo``; None (and a message) if any request fails."""
    got = []
    for k, u in enumerate(urls(model, todo)):
        if k:
            time.sleep(pause())
        try:
            resp = http_json(u)
        except Exception as e:  # noqa: BLE001 - any failure: keep what is saved
            print(f"{model}: download failed ({e})", file=sys.stderr)
            return None
        if isinstance(resp, dict):  # an error body (one point would be a dict too)
            print(f"{model}: {resp.get('reason', 'no data')}", file=sys.stderr)
            return None
        got.append((u, resp))
    return got


def model_grid(
    saved: dict[str, Any] | None, model: str, todo: list[str], now: dt.datetime, *, force: bool
) -> tuple[list[tuple[str, Any]] | None, dt.datetime]:
    """Return a model's grid for ``todo`` and when it was pulled: saved if recent, else new.

    The saved grid is kept while it covers ``todo`` and is younger than MAX_AGE (unless
    ``force``), and whenever the download fails.
    """
    old = saved_set(saved, model)
    stamp = now
    if old and saved:
        stamp = dt.datetime.fromisoformat(min(saved["__fetched__"][u] for u, _ in old))
        if (
            not force
            and now - stamp < MAX_AGE[model]
            and all(covers([p for _, r in old for p in r], d) for d in todo)
        ):
            print(f"{model}: kept the saved grid from {stamp:%Y-%m-%d %H:%M} UTC", file=sys.stderr)
            return old, stamp  # recent enough: no requests
    got = download(model, todo)
    if got is None and old:
        return old, stamp  # the download failed: keep the saved grid
    return got, now


def fetch(
    days: list[str], now: dt.datetime | None = None, *, force: bool = False
) -> dict[str, str]:
    """Update CACHE for the ``days`` not yet over; return the model drawing each day.

    Never raises for a download problem, and never replaces the saved grid with one that
    covers fewer days. Each model's saved grid is reused while it is younger than
    MAX_AGE (unless ``force``) or when its download fails.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    saved = load()
    days = live_days(days, now)
    lats, lons = grid()
    data: dict[str, Any] = {
        "__fetched__": {},
        "__grid__": {"lats": lats, "lons": lons, "fade": FADE},
        "__days__": {},
        "__sets__": {},
    }
    for model in MODELS:
        todo = [d for d in days if d not in data["__days__"]]
        if model == "ncep_hrrr_conus":
            todo = hrrr_days(todo, now)
        if not todo:
            continue
        got, when = model_grid(saved, model, todo, now, force=force)
        if not got:
            continue
        used = [d for d in todo if covers([p for _, r in got for p in r], d)]
        if not used:
            print(f"{model} covers none of {', '.join(todo)}", file=sys.stderr)
            continue
        data["__days__"].update(dict.fromkeys(used, model))
        data["__sets__"][model] = [u for u, _ in got]
        for u, r in got:  # saved only when it draws a day
            data[u] = r
            data["__fetched__"][u] = when.isoformat(timespec="seconds")
    missing = [d for d in days if d not in data["__days__"]]
    if missing:
        print(f"no model covers {', '.join(missing)}; maps keep the coarse layer", file=sys.stderr)
    before = [d for d in days if d in (saved or {}).get("__days__", {})]
    if saved and len(data["__days__"]) < len(before):
        print("the new grid covers fewer days; kept the saved one", file=sys.stderr)
        return dict(saved["__days__"])
    CACHE.write_text(json.dumps(data), encoding="utf-8")
    return dict(data["__days__"])


def export(path: Path = EXPORT) -> Path | None:
    """Write the saved grid for puff_dispersal.py --sky-grid; None if nothing is saved.

    One series per model, in MODELS order; the model run picks the first that covers its
    hours.
    """
    saved = load()
    if not saved or "__grid__" not in saved:
        return None
    fetched = saved["__fetched__"]
    series = []
    for model in MODELS:
        parts = saved["__sets__"].get(model)
        if not parts:
            continue
        hourly = [p["hourly"] for u in parts for p in saved[u]]
        series.append(
            {
                "model": model,
                "fetched": min(fetched[u] for u in parts),
                "times": [s + "Z" for s in hourly[0]["time"]],
                # [time][point], points row by row from the south-west corner
                "cloud": [list(c) for c in zip(*(h["cloud_cover"] for h in hourly), strict=True)],
                "precip": [
                    list(c) for c in zip(*(h["precipitation"] for h in hourly), strict=True)
                ],
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({**saved["__grid__"], "series": series}), encoding="utf-8")
    return path


def site_days() -> list[str]:
    """Return every day the site and the staged maps model."""
    import make_map_picker as site  # noqa: PLC0415
    import staged  # noqa: PLC0415

    return sorted({d for d, _ in site.DAYS} | set(staged.DAYS))


def main(argv: list[str] | None = None) -> None:
    """Fetch the grid (--fetch [--force]) or say what is saved."""
    args = sys.argv[1:] if argv is None else argv
    if args not in ([], ["--fetch"], ["--fetch", "--force"]):
        raise SystemExit("usage: sky_grid.py [--fetch [--force]]")
    sys.path.insert(0, str(HERE))
    if args:
        chosen = fetch(site_days(), force="--force" in args)
        for d, m in sorted(chosen.items()):
            print(f"{d}: {m}")
        return
    saved = load()
    if not saved or "__grid__" not in saved:
        print(f"nothing saved at {CACHE}")
        return
    g = saved["__grid__"]
    print(
        f"{len(g['lats'])} x {len(g['lons'])} points, pulled {min(saved['__fetched__'].values())}"
    )
    for d, m in sorted(saved["__days__"].items()):
        print(f"{d}: {m}")


if __name__ == "__main__":
    main()
