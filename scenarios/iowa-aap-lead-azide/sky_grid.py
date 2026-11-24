#!/usr/bin/env python3
"""Forecast cloud cover and precipitation on a finer grid, for the maps' weather layer.

Display only: the lead model keeps its own 5x5 weather grid (met_cache/map_met_all.json),
whose points are about 90 miles apart, so nothing here changes the lead results. This
grid has points SPACING degrees apart (about 20 miles) around the plant, from one model:
HRRR (NOAA, 3 km, run every hour) for a run it covers, else GFS (NOAA's global model,
covering the full forecast range). HRRR reaches about 18 to 48 hours ahead, depending on
the run, so GFS draws the layer for blasts further out and HRRR takes over closer in.

    python3 sky_grid.py --fetch   # download into met_cache/sky_grid.json (uses the network)
    python3 sky_grid.py           # say what is saved

The site build only reads the saved file (export()); it never downloads. A forecast
refresh (tools/refresh_forecast.py) fetches it together with the lead model's forecasts.

Open-Meteo counts each point as a request: one fetch costs about 475 for HRRR, plus as
many again when GFS is needed, against a free limit of about 10,000 a day that the
3-hourly refresh already uses part of (README "Open-Meteo limits").
"""

from __future__ import annotations

import datetime as dt
import json
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
LAT, LON = 40.83, -91.27  # the plant, rounded
SPACING = 0.3  # degrees between points (about 21 miles north-south)
N_LAT, N_LON = 9, 12  # points each side of the plant: 19 x 25 = 475 points
#: Tried in this order; the first that covers a map's whole run is shown on it.
MODELS = ("ncep_hrrr_conus", "gfs_seamless")
VARS = ("cloud_cover", "precipitation")
#: The hours every map can need, in Central standard time: the earliest blast (11:00)
#: to the latest (13:00) plus the 8-hour run and an hour to spare.
FIRST, LAST = dt.time(11), dt.timedelta(hours=11)
CST = dt.timezone(dt.timedelta(hours=-6))


def grid() -> tuple[list[float], list[float]]:
    """Return the grid's latitudes and longitudes, south to north and west to east."""
    lats = [round(LAT + SPACING * k, 2) for k in range(-N_LAT, N_LAT + 1)]
    lons = [round(LON + SPACING * k, 2) for k in range(-N_LON, N_LON + 1)]
    return lats, lons


def url(model: str, days: list[str]) -> str:
    """Open-Meteo request for every grid point, latitude rows south to north."""
    lats, lons = grid()
    last = dt.date.fromisoformat(max(days)) + dt.timedelta(days=1)  # runs end after midnight
    params = {
        "latitude": ",".join(f"{la:.2f}" for la in lats for _ in lons),
        "longitude": ",".join(f"{lo:.2f}" for _ in lats for lo in lons),
        "hourly": ",".join(VARS),
        "models": model,
        "timezone": "GMT",
        "start_date": min(days),
        "end_date": last.isoformat(),
    }
    return URL + "?" + urllib.parse.urlencode(params, safe=",")


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


def fetch(days: list[str]) -> dict[str, str]:
    """Download the grid for ``days`` into CACHE; return the model chosen for each day."""
    data: dict[str, Any] = {"__fetched__": {}}
    chosen: dict[str, str] = {}
    for model in MODELS:
        todo = [d for d in days if d not in chosen]
        if not todo:
            break
        u = url(model, days)
        resp = http_json(u)
        if isinstance(resp, dict):  # one point would be a dict; an error is one too
            print(f"{model}: {resp.get('reason', 'no data')}", file=sys.stderr)
            continue
        used = [d for d in todo if covers(resp, d)]
        if not used:
            print(f"{model} covers none of {', '.join(todo)}", file=sys.stderr)
            continue
        chosen.update(dict.fromkeys(used, model))
        data[u] = resp  # saved only when it draws a day
        data["__fetched__"][u] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    missing = [d for d in days if d not in chosen]
    if missing:
        print(
            f"no model covers {', '.join(missing)}; the maps keep the coarse layer", file=sys.stderr
        )
    CACHE.write_text(json.dumps(data), encoding="utf-8")
    return chosen


def export(path: Path = EXPORT) -> Path | None:
    """Write the saved grid for puff_dispersal.py --sky-grid; None if nothing is saved.

    One series per saved response, in MODELS order; the model run picks the first that
    covers its hours.
    """
    if not CACHE.exists():
        return None
    saved = json.loads(CACHE.read_text(encoding="utf-8"))
    fetched = saved.get("__fetched__", {})
    lats, lons = grid()
    series = []
    for model in MODELS:
        for u, points in saved.items():
            if u == "__fetched__" or f"models={model}" not in u:
                continue
            hourly = [p["hourly"] for p in points]
            series.append(
                {
                    "model": model,
                    "fetched": fetched.get(u),
                    "times": [s + "Z" for s in hourly[0]["time"]],
                    # [time][point], points row by row from the south-west corner
                    "cloud": [
                        list(col) for col in zip(*(h["cloud_cover"] for h in hourly), strict=True)
                    ],
                    "precip": [
                        list(col) for col in zip(*(h["precipitation"] for h in hourly), strict=True)
                    ],
                }
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"lats": lats, "lons": lons, "series": series}), encoding="utf-8")
    return path


def site_days() -> list[str]:
    """Every day the site and the staged maps model."""
    import make_map_picker as site  # noqa: PLC0415
    import staged  # noqa: PLC0415

    return sorted({d for d, _ in site.DAYS} | set(staged.DAYS))


def main(argv: list[str] | None = None) -> None:
    """Fetch the grid (--fetch) or say what is saved."""
    args = sys.argv[1:] if argv is None else argv
    if args and args != ["--fetch"]:
        raise SystemExit("usage: sky_grid.py [--fetch]")
    sys.path.insert(0, str(HERE))
    if args:
        chosen = fetch(site_days())
        for d, m in chosen.items():
            print(f"{d}: {m}")
        return
    if not CACHE.exists():
        print(f"nothing saved at {CACHE}")
        return
    saved = json.loads(CACHE.read_text(encoding="utf-8"))
    for u, points in saved.items():
        if u != "__fetched__":
            days = [d for d in site_days() if covers(points, d)]
            model = urllib.parse.parse_qs(urllib.parse.urlparse(u).query)["models"][0]
            pulled = saved["__fetched__"].get(u)
            print(f"{model}, pulled {pulled}: covers {', '.join(days) or 'no day'}")


if __name__ == "__main__":
    main()
