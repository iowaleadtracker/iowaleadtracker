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

--fetch keeps the saved grid while it is under MAX_AGE old and no day needs HRRR (GFS
runs every 6 hours, so a newer download would usually hold the same run); --force
downloads anyway. The site build only reads the saved file (export()); it never
downloads. A forecast refresh (tools/refresh_forecast.py) runs --fetch with the lead
model's forecasts.

Open-Meteo counts each point as a request: a download costs about 770 per model, against
a free limit of about 10,000 a day that the 3-hourly refresh already uses part of
(README "Open-Meteo limits").
"""

from __future__ import annotations

import datetime as dt
import json
import math
import sys
import urllib.parse
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))  # the repo root, for dispersal.met

from dispersal.met import http_json  # noqa: E402

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
MAX_AGE = dt.timedelta(hours=6)  # keep a saved grid this long when no day needs HRRR
VARS = ("cloud_cover", "precipitation")
#: The hours every map can need, in Central standard time: the earliest blast (11:00)
#: to the latest (13:00) plus the 8-hour run and an hour to spare.
FIRST, LAST = dt.time(11), dt.timedelta(hours=11)
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


def hrrr_days(days: list[str], now: dt.datetime) -> list[str]:
    """Return the days whose maps end within HRRR_HOURS of ``now``."""
    return [d for d in days if window(d)[1] <= now + dt.timedelta(hours=HRRR_HOURS)]


def load() -> dict[str, Any] | None:
    """Return the saved grid file, or None."""
    return json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else None


def still_good(saved: dict[str, Any] | None, days: list[str], now: dt.datetime) -> bool:
    """Return True if the saved grid can stand: same points, every day, recent, no HRRR."""
    if not saved or hrrr_days(days, now):
        return False
    lats, lons = grid()
    if saved.get("__grid__") != {"lats": lats, "lons": lons, "fade": FADE}:
        return False
    if not set(days) <= set(saved.get("__days__", {})):
        return False
    stamps = [dt.datetime.fromisoformat(v) for v in saved.get("__fetched__", {}).values()]
    return bool(stamps) and now - min(stamps) < MAX_AGE


def fetch(
    days: list[str], now: dt.datetime | None = None, *, force: bool = False
) -> dict[str, str]:
    """Download the grid for ``days`` into CACHE; return the model chosen for each day.

    Keeps the saved grid instead when still_good() says so, unless ``force``.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    saved = load()
    if not force and still_good(saved, days, now):
        print("kept the saved weather grid (recent, and no day needs HRRR)", file=sys.stderr)
        return dict(saved["__days__"])  # type: ignore[index]
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
        got = []
        for u in urls(model, todo):
            resp = http_json(u)
            if isinstance(resp, dict):  # an error (or a single point)
                print(f"{model}: {resp.get('reason', 'no data')}", file=sys.stderr)
                break
            got.append((u, resp))
        else:
            points = [p for _, r in got for p in r]
            used = [d for d in todo if covers(points, d)]
            if not used:
                print(f"{model} covers none of {', '.join(todo)}", file=sys.stderr)
                continue
            data["__days__"].update(dict.fromkeys(used, model))
            data["__sets__"][model] = [u for u, _ in got]
            stamp = now.isoformat(timespec="seconds")
            for u, r in got:  # saved only when it draws a day
                data[u] = r
                data["__fetched__"][u] = stamp
    missing = [d for d in days if d not in data["__days__"]]
    if missing:
        print(f"no model covers {', '.join(missing)}; maps keep the coarse layer", file=sys.stderr)
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
