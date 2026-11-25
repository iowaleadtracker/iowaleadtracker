"""Weather: Open-Meteo download and cache, the gridded met field, transport winds."""

from __future__ import annotations

import datetime as dt
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from .constants import R_EARTH
from .dispersion import DEFAULT_BLH, PROFILE_P, stability_class

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from .types import FloatArray, IntArray, Json, MetArray


HOURLY_VARS = [
    "wind_speed_10m",
    "wind_direction_10m",
    "cloud_cover",
    "shortwave_radiation",
    "precipitation",
    "boundary_layer_height",
]


STD_PRESSURE_LEVELS = [1000, 975, 950, 925, 900, 850, 800, 700, 600, 500]  # hPa


#: Near-surface wind level aloft (m) asked of the forecast API, and of named models that
#: serve a different one. Open-Meteo's HRRR has 80 m wind but no 120 m (every value comes
#: back empty), so before Nov. 25, 2026 HRRR runs used a power-law guess from 10 m instead.
FORECAST_WIND_ALOFT_M = 120
MODEL_WIND_ALOFT_M = {"ncep_hrrr_conus": 80}


# Built-in weather-model ensemble for --weather-model ensemble (Open-Meteo model names; the
# Iowa site passes its own list). The first is the run shown;
# the rest feed the uncertainty view. HRRR is used only when it covers the whole run.
WEATHER_ENSEMBLE = [
    "ecmwf_ifs025",
    "gfs_seamless",
    "icon_seamless",
    "gem_seamless",
    "ukmo_seamless",
    "meteofrance_seamless",
    "ncep_hrrr_conus",
]


MODEL_RESIDUAL_DEG = 5.0  # direction error allowed around each weather model


#: --met-cache state: the JSON file that stores Open-Meteo responses, and its contents.
MET_CACHE: dict[str, Any] = {"path": None, "data": None}


_RETRY_STATUS = (429, 500, 502, 503, 504)


#: Set (to any value) by the site build when every forecast should already be saved: a request
#: that isn't in the saved file then stops the run with :class:`NotSaved` instead of downloading.
CACHE_ONLY_ENV = "PUFF_MET_CACHE_ONLY"
#: The command line's exit status for :class:`NotSaved`.
NOT_SAVED_EXIT = 3


class NotSaved(BaseException):
    """A forecast the run needs isn't saved and downloads are off (``CACHE_ONLY_ENV``).

    A BaseException, so the per-model fallbacks (``except Exception``) can't swallow it and
    quietly build a map from fewer weather models.
    """


#: Key in the cache file for requests that failed when they were downloaded: URL ->
#: {"code": HTTP status or None, "detail": text}. With downloads off they fail the same way
#: again (:class:`SavedFailure`), so a replay takes the same fallbacks the download did.
FAILED_KEY = "__failed__"


class SavedFailure(Exception):  # noqa: N818 - named for what it is, a replayed failure
    """A request that failed when the forecasts were downloaded, replayed with downloads off.

    An ordinary Exception, unlike :class:`NotSaved`: the fallbacks (fewer variables, the
    next source, the next weather model) handle it exactly as they handled the original
    failure. ``code`` is the HTTP status, or None.
    """

    def __init__(self, url: str, code: int | None, detail: str) -> None:
        super().__init__(f"{detail} (failed when downloaded: {url})")
        self.code = code


#: Environment variable holding an Open-Meteo commercial API key. When it is set,
#: requests go to the customer servers with the key; without it, to the free API.
API_KEY_ENV = "OPEN_METEO_API_KEY"

#: Free API host -> commercial (customer) host.
_CUSTOMER_HOSTS = {
    "api.open-meteo.com": "customer-api.open-meteo.com",
    "archive-api.open-meteo.com": "customer-archive-api.open-meteo.com",
}


def _request_url(url: str) -> str:
    """Return the address to send ``url`` to: the customer API with the key, if one is set.

    Everything else (the cache keys, the saved forecasts, error messages) uses the
    free-API address, so the key is never written to a file and saved forecasts still
    match whether or not a key is set.
    """
    key = os.environ.get(API_KEY_ENV, "").strip()
    parts = urllib.parse.urlsplit(url)
    host = _CUSTOMER_HOSTS.get(parts.netloc)
    if not key or host is None:
        return url
    query = "&".join(q for q in (parts.query, urllib.parse.urlencode({"apikey": key})) if q)
    return urllib.parse.urlunsplit(parts._replace(netloc=host, query=query))


def _cache_lookup(url: str) -> Any:  # noqa: ANN401 - Open-Meteo JSON (object or list)
    """Return the cached response for ``url``, loading the cache file on first use."""
    if not MET_CACHE["path"]:
        return None
    if MET_CACHE["data"] is None:
        MET_CACHE["data"] = {}
        path = Path(MET_CACHE["path"])
        if path.exists():
            with path.open(encoding="utf-8") as f:
                MET_CACHE["data"] = json.load(f)
    return MET_CACHE["data"].get(url)


def _cache_store(url: str, data: Any) -> None:  # noqa: ANN401 - Open-Meteo JSON
    """Save a good response, with its download time, to the cache file."""
    if not MET_CACHE["path"] or (isinstance(data, dict) and data.get("error")):
        return
    MET_CACHE["data"][url] = data
    MET_CACHE["data"].get(FAILED_KEY, {}).pop(url, None)
    # when each response was downloaded, so pages can say how old the forecast is
    MET_CACHE["data"].setdefault("__fetched__", {})[url] = dt.datetime.now(
        dt.timezone.utc
    ).isoformat(timespec="seconds")
    with Path(MET_CACHE["path"]).open("w", encoding="utf-8") as f:
        json.dump(MET_CACHE["data"], f)


def _cache_failure(url: str, code: int | None, detail: str) -> None:
    """Record in the cache file that ``url`` failed, so a replay fails the same way."""
    if not MET_CACHE["path"]:
        return
    MET_CACHE["data"].setdefault(FAILED_KEY, {})[url] = {"code": code, "detail": detail}
    with Path(MET_CACHE["path"]).open("w", encoding="utf-8") as f:
        json.dump(MET_CACHE["data"], f)


def _saved(url: str) -> Any:  # noqa: ANN401 - Open-Meteo JSON
    """Return the saved response for ``url``, or None to download it.

    With downloads off (``CACHE_ONLY_ENV``), a request that failed when it was downloaded
    fails again (:class:`SavedFailure`) and one never made stops the run (:class:`NotSaved`).
    """
    cached = _cache_lookup(url)
    if cached is not None or not os.environ.get(CACHE_ONLY_ENV):
        return cached
    failed = (MET_CACHE["data"] or {}).get(FAILED_KEY, {}).get(url)
    if failed is not None:
        raise SavedFailure(url, failed.get("code"), str(failed.get("detail", "")))
    raise NotSaved(url)


def http_json(url: str, timeout: float = 60, tries: int = 4) -> Any:  # noqa: ANN401
    """GET a JSON document, retrying rate limits (429) and server errors with backoff.

    With ``--met-cache``, responses are stored in (and replayed from) a JSON file, so a
    rerun makes no requests. With OPEN_METEO_API_KEY set, Open-Meteo requests use the
    commercial API (see ``_request_url``); ``url`` stays the cache key either way.
    """
    cached = _saved(url)
    if cached is not None:
        return cached
    if not url.startswith("https://"):
        raise ValueError(f"refusing non-HTTPS URL {url!r}")
    req = urllib.request.Request(  # noqa: S310 - HTTPS checked above
        _request_url(url), headers={"User-Agent": "puff-dispersal/1.0"}
    )
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - HTTPS checked above
                data = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code not in _RETRY_STATUS or attempt == tries - 1:
                _cache_failure(url, e.code, str(e))
                raise
        except OSError as e:  # URLError, connection resets, timeouts
            if attempt == tries - 1:
                _cache_failure(url, None, str(e))
                raise
        else:
            if isinstance(data, dict) and data.get("error"):
                # refused in the body; not saved as a forecast, but replayed as a refusal
                _cache_failure(url, None, str(data.get("reason", "error")))
                return data
            _cache_store(url, data)
            return data
        time.sleep(2**attempt * 2)
    raise RuntimeError(f"no response from {url}")  # pragma: no cover - loop always returns


def pressure_levels_for(elev_m: float | None, n: int = 6) -> list[int]:
    """Return the standard pressure levels (hPa) that sit above the ground at this elevation.

    Surface pressure from the standard-atmosphere barometric formula; a level must be
    at least 20 hPa below it.
    """
    p_sfc = 1013.25 * (1.0 - 2.25577e-5 * max(elev_m or 0.0, 0.0)) ** 5.25588
    return [p for p in STD_PRESSURE_LEVELS if p < p_sfc - 20.0][:n]


def _open_meteo_url(
    base: str,
    base_params: dict[str, str],
    z_up: int,
    levs: Sequence[int],
    *,
    upper: bool,
    extra: Sequence[str] = (),
) -> str:
    """Request URL for the hourly variables, optional wind aloft and pressure levels.

    ``extra`` adds hourly variables after the standard ones (``--spread turbulence``
    asks for ``temperature_2m``); without it the URL, and so the cache key, is unchanged.
    """
    hourly = list(HOURLY_VARS) + list(extra)
    if upper:
        hourly += [f"wind_speed_{z_up}m", f"wind_direction_{z_up}m"]
    for lv in levs:
        hourly += [
            f"wind_speed_{lv}hPa",
            f"wind_direction_{lv}hPa",
            f"geopotential_height_{lv}hPa",
        ]
    params = dict(base_params, hourly=",".join(hourly))
    return base + "?" + urllib.parse.urlencode(params, safe=",")


def _error_detail(e: Exception) -> str:
    """Open-Meteo's ``reason`` from an HTTP error body, else the exception text."""
    try:
        return str(json.loads(e.read().decode()).get("reason"))  # type: ignore[attr-defined]
    except (AttributeError, ValueError, OSError):
        return str(e)


def _data_problem(
    data: Any,  # noqa: ANN401 - Open-Meteo JSON
    start: dt.datetime | None = None,
    end: dt.datetime | None = None,
) -> str | None:
    """Describe why a response can't be used, or return None if it can.

    Only the hours from ``start`` to ``end`` (the run) count when they are given: a
    request covers whole days, and a model that stops after the run is still usable.
    """
    if isinstance(data, dict) and data.get("error"):
        return str(data.get("reason"))
    points = data if isinstance(data, list) else [data]
    ws = np.array([d["hourly"]["wind_speed_10m"] for d in points], dtype=float)
    times = points[0]["hourly"].get("time") if points else None
    if start is not None and end is not None and start.tzinfo is not None and times:
        t = [dt.datetime.fromisoformat(s_).replace(tzinfo=dt.timezone.utc) for s_ in times]
        keep = [i for i, ti in enumerate(t) if start <= ti <= end]
        if keep:
            ws = ws[:, keep]
    if np.isnan(ws).mean() > 0.2:
        return "data missing for the requested period"
    return None


def fetch_open_meteo(
    lats: Sequence[float] | FloatArray,
    lons: Sequence[float] | FloatArray,
    start: dt.datetime,
    end: dt.datetime,
    levels: Sequence[int] = (),
    model: str | None = None,
    now: dt.datetime | None = None,
    extra: Sequence[str] = (),
) -> tuple[str, list[Json], int | None, list[int]]:
    """Hourly weather for the given points from Open-Meteo.

    ``now`` is the time the choice of source is made against (default: the clock). Set
    it to when saved forecasts were pulled to replay them on a later date.

    Picks the ERA5 archive for past dates and the forecast API otherwise. Also asks
    for one near-surface wind level aloft (100 m in ERA5; 120 m in the forecast API, or
    the model's own level from ``MODEL_WIND_ALOFT_M``, e.g. 80 m for HRRR)
    and, when ``levels`` is given, wind and geopotential height on those pressure
    levels (served by the forecast API; the archive returns none). If a request is
    refused, retries with fewer variables, then tries the other source.

    Returns
    -------
    tuple
        Source name, the per-point responses, the height of the wind level aloft (or
        None) and the pressure levels requested.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    base_params = {
        "latitude": ",".join(f"{v:.4f}" for v in lats),
        "longitude": ",".join(f"{v:.4f}" for v in lons),
        "wind_speed_unit": "ms",
        "timezone": "GMT",
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date": end.strftime("%Y-%m-%d"),
    }
    archive = (
        "ERA5 reanalysis (Open-Meteo archive)",
        "https://archive-api.open-meteo.com/v1/archive",
        100,
    )
    forecast = (
        "Open-Meteo forecast (best-match NWP)",
        "https://api.open-meteo.com/v1/forecast",
        FORECAST_WIND_ALOFT_M,
    )
    if end > now + dt.timedelta(days=15.5):
        raise SystemExit("Forecast data only reaches ~16 days ahead; pick an earlier time.")
    order = [archive, forecast] if end < now - dt.timedelta(days=6) else [forecast, archive]
    if model:  # a named forecast model: only the forecast API serves it
        base_params["models"] = model
        z_model = MODEL_WIND_ALOFT_M.get(model, forecast[2])
        order = [(f"Open-Meteo forecast, {model}", forecast[1], z_model)]
    tiers: list[tuple[bool, tuple[int, ...]]] = [(True, tuple(levels)), (True, ()), (False, ())]
    if not levels:
        tiers = tiers[1:]
    errors = []
    for name, base, z_up in order:
        for upper, levs in tiers:
            url = _open_meteo_url(base, base_params, z_up, levs, upper=upper, extra=extra)
            try:
                data = http_json(url)
            except Exception as e:  # noqa: BLE001 - every failure is reported, then the next try
                errors.append(f"{name}: {_error_detail(e)}")
                if upper and getattr(e, "code", None) == 400:
                    continue  # maybe an upper-level variable; retry with fewer
                break
            problem = _data_problem(data, start, end)
            if problem:
                errors.append(f"{name}: {problem}")
                break
            points = data if isinstance(data, list) else [data]
            source = name
            if "archive" in base and end > now - dt.timedelta(days=6):
                source = "Open-Meteo archive (recent days: preliminary model data, not final ERA5)"
            return source, points, (z_up if upper else None), list(levs)
    raise SystemExit("Could not get weather data:\n  " + "\n  ".join(errors))


class MetField:
    """Hourly weather on a regular lat/lon grid, interpolated to puff positions.

    Fields are arrays (hours, ny, nx): ``u``, ``v`` (10 m wind components), ``u_up``,
    ``v_up`` (wind at ``z_up``), ``ws``, ``wd``, ``cloud``, ``sw``, ``precip``, ``stab``
    (class index), ``blh`` (mixing height, m), and for each pressure level ``k`` its
    height above ground ``zl{k}`` and wind ``ul{k}``, ``vl{k}``. With ``--spread
    turbulence`` also ``t2`` (2 m air temperature, K) when the source has it.
    """

    def __init__(
        self,
        t0_hour: dt.datetime,
        lat_nodes: FloatArray,
        lon_nodes: FloatArray,
        fields: dict[str, MetArray],
        z_up: float = 100.0,
        n_lev: int = 0,
        level_names: Iterable[str] = (),
    ) -> None:
        self.t0 = t0_hour  # aware datetime of index 0
        self.z_up = z_up  # height of the upper wind level, m
        # pressure-level winds, lowest first: fields zl{k} (m above ground), ul{k}, vl{k}
        self.n_lev = n_lev
        self.level_names = list(level_names)
        self.lat_nodes, self.lon_nodes = lat_nodes, lon_nodes
        self.f = fields  # name -> array (T, ny, nx)
        self.nt = fields["u"].shape[0]

    @staticmethod
    def _idx(arr: FloatArray, v: FloatArray) -> tuple[IntArray, FloatArray]:
        """Lower node index and linear weight of each value along one axis."""
        if len(arr) == 1:
            return np.zeros_like(v, int), np.zeros_like(v)
        i = np.clip(np.searchsorted(arr, v) - 1, 0, len(arr) - 2)
        w = np.clip((v - arr[i]) / (arr[i + 1] - arr[i]), 0.0, 1.0)
        return i, w

    def sample(
        self,
        name: str,
        th: FloatArray,
        lat: FloatArray,
        lon: FloatArray,
        *,
        nearest: bool = False,
    ) -> FloatArray:
        """Field ``name`` at fractional met hours ``th`` and positions ``lat``, ``lon``.

        Trilinear interpolation in time, latitude and longitude, or the nearest node
        and hour (for class indices).
        """
        it = np.clip(np.floor(th).astype(int), 0, self.nt - 2)
        wt = np.clip(th - it, 0.0, 1.0)
        iy, wy = self._idx(self.lat_nodes, lat)
        ix, wx = self._idx(self.lon_nodes, lon)
        a = self.f[name]
        ny, nx = a.shape[1:]
        iy1, ix1 = np.minimum(iy + 1, ny - 1), np.minimum(ix + 1, nx - 1)
        if nearest:
            yy = np.where(wy > 0.5, iy1, iy)
            xx = np.where(wx > 0.5, ix1, ix)
            near: FloatArray = a[it + (wt > 0.5), yy, xx]
            return near
        out: Any = 0.0
        for tt, w_t in ((it, 1 - wt), (it + 1, wt)):
            out = out + w_t * (
                (1 - wy) * ((1 - wx) * a[tt, iy, ix] + wx * a[tt, iy, ix1])
                + wy * ((1 - wx) * a[tt, iy1, ix] + wx * a[tt, iy1, ix1])
            )
        result: FloatArray = out
        return result


def _hour_index(points: list[Json], t_first: dt.datetime) -> tuple[list[dt.datetime], int]:
    """Return the response's hourly times (UTC) and the index of ``t_first`` in them."""
    times = [
        dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc)
        for s in points[0]["hourly"]["time"]
    ]
    return times, times.index(t_first)


def _constant_wind_met(
    lat0: float,
    lon0: float,
    t_first: dt.datetime,
    t_last: dt.datetime,
    constant_wind: tuple[float, float],
) -> MetField:
    """Build a uniform, steady, neutral (class D) met field for ``--wind SPEED@DIR``."""
    speed, dirn = constant_wind
    nt = math.ceil((t_last - t_first).total_seconds() / 3600) + 2
    th = math.radians(dirn)
    shape = (nt, 1, 1)
    fields = {
        "u": np.full(shape, -speed * math.sin(th)),
        "v": np.full(shape, -speed * math.cos(th)),
        # neutral (class D) power law to the 100 m level
        "u_up": np.full(shape, -speed * math.sin(th) * 10 ** PROFILE_P[3]),
        "v_up": np.full(shape, -speed * math.cos(th) * 10 ** PROFILE_P[3]),
        "ws": np.full(shape, speed),
        "wd": np.full(shape, dirn % 360),
        "cloud": np.full(shape, 100.0),
        "sw": np.zeros(shape),
        "precip": np.zeros(shape),
        "stab": np.full(shape, 3),
        "blh": np.full(shape, 800.0),
    }
    return MetField(t_first, np.array([lat0]), np.array([lon0]), fields)


def _check_model_covers(src: list[Json], t_first: dt.datetime, hours: int, model: str) -> None:
    """Raise ValueError unless a named model has wind data for the whole run."""
    t_all = [
        dt.datetime.fromisoformat(s_).replace(tzinfo=dt.timezone.utc)
        for s_ in src[0]["hourly"]["time"]
    ]
    k0 = t_all.index(t_first)
    w = list(src[0]["hourly"]["wind_speed_10m"][k0 : k0 + hours + 2])
    if len(w) < hours + 2 or any(x is None for x in w):
        raise ValueError(f"{model} does not cover the whole run")


def _stack(data: list[Json], var: str, fill: float, ny: int, nx: int) -> FloatArray:
    """One hourly variable as an array (T, ny, nx), gaps filled forward, back, then ``fill``."""
    arr = np.array(
        [[np.nan if v is None else v for v in d["hourly"][var]] for d in data], float
    )  # (npts, T)
    arr = arr.T.reshape(-1, ny, nx)
    # Fill gaps forward/backward in time, then with a default.
    for k in range(1, arr.shape[0]):
        arr[k] = np.where(np.isnan(arr[k]), arr[k - 1], arr[k])
    for k in range(arr.shape[0] - 2, -1, -1):
        arr[k] = np.where(np.isnan(arr[k]), arr[k + 1], arr[k])
    out: FloatArray = np.where(np.isnan(arr), fill, arr)
    return out


def _wind_components(ws: FloatArray, wd_deg: FloatArray) -> tuple[FloatArray, FloatArray]:
    """Eastward and northward components of a wind blowing FROM ``wd_deg``."""
    th = np.radians(wd_deg)
    return -ws * np.sin(th), -ws * np.cos(th)


@dataclass
class _MetSource:
    """What Open-Meteo returned for the wind grid."""

    name: str
    data: list[Json]
    z_up: int | None
    levels: list[int]
    lat_nodes: FloatArray
    lon_nodes: FloatArray


def _fetch_wind_grid(  # noqa: PLR0913 - the request's own settings
    lat0: float,
    lon0: float,
    t_first: dt.datetime,
    t_last: dt.datetime,
    hours: int,
    grid_n: int,
    *,
    use_levels: bool,
    model: str | None,
    now: dt.datetime | None = None,
    extra: Sequence[str] = (),
) -> tuple[_MetSource, float | None]:
    """Fetch the source point, size the wind grid from the wind there, then fetch the grid.

    Returns the grid data and the ground elevation at the source (m), if known.
    """
    # Stage 1: winds at the source, to size the wind grid and pick pressure levels.
    src_name, src, z_up, _ = fetch_open_meteo(
        [lat0], [lon0], t_first, t_last, model=model, now=now, extra=extra
    )
    if model:  # a named model must really cover the run (some stop after 18-48 h)
        _check_model_covers(src, t_first, hours, model)
    levels = pressure_levels_for(src[0].get("elevation")) if use_levels else []
    _, i0 = _hour_index(src, t_first)
    ws = np.array(src[0]["hourly"]["wind_speed_10m"], float)
    # m; winds aloft are faster than the 10 m wind, more so where real upper-level
    # winds are used (forecast source) than with the power-law profile
    reach = (
        np.nansum(ws[i0 : i0 + hours + 1])
        * 3600.0
        * (2.2 if levels and "forecast" in src_name else 1.6)
    )
    reach = float(np.clip(reach, 20e3, 1500e3))
    if grid_n > 1:
        dlat = math.degrees(reach / R_EARTH)
        dlon = math.degrees(reach / (R_EARTH * math.cos(math.radians(lat0))))
        lat_nodes = np.linspace(lat0 - dlat, lat0 + dlat, grid_n).clip(-89.5, 89.5)
        lon_nodes = np.linspace(lon0 - dlon, lon0 + dlon, grid_n)
        LA, LO = np.meshgrid(lat_nodes, lon_nodes, indexing="ij")
        name, data, z_up, levels = fetch_open_meteo(
            LA.ravel(),
            ((LO.ravel() + 180) % 360) - 180,
            t_first,
            t_last,
            levels,
            model,
            now,
            extra,
        )
        if name != src_name:
            print(f"note: grid used {name}, source used {src_name}", file=sys.stderr)
    else:
        lat_nodes, lon_nodes, name = np.array([lat0]), np.array([lon0]), src_name
        data = src
        if levels:
            name, data, z_up, levels = fetch_open_meteo(
                [lat0], [lon0], t_first, t_last, levels, model, now, extra
            )
    return _MetSource(name, data, z_up, levels, lat_nodes, lon_nodes), src[0].get("elevation")


def _pressure_level_fields(
    data: list[Json],
    levels: Sequence[int],
    shape: tuple[int, int],
    lowest: tuple[FloatArray, FloatArray, FloatArray],
) -> tuple[dict[str, MetArray], list[str]]:
    """Winds on pressure levels as height above each node's ground, lowest first.

    Levels without data are skipped. A level below (or within 30 m of) the one under
    it, e.g. under ground, carries that lower level's wind up instead. ``lowest`` is
    (height, u, v) of the wind level aloft that the pressure levels continue from.
    """
    ny, nx = shape
    fields: dict[str, MetArray] = {}
    used: list[str] = []
    elev_nodes = np.array([d.get("elevation") or 0.0 for d in data], float).reshape(ny, nx)
    z_prev, u_prev, v_prev = lowest
    for lv in levels:
        raw = np.array(
            [
                [
                    np.nan if x is None else x
                    for x in d["hourly"].get(f"geopotential_height_{lv}hPa", [None])
                ]
                for d in data
            ],
            float,
        )
        if raw.size == 0 or np.isnan(raw).mean() > 0.5:
            continue  # this source has no data on the level
        gh = _stack(data, f"geopotential_height_{lv}hPa", np.nan, ny, nx)
        ws_l = _stack(data, f"wind_speed_{lv}hPa", np.nan, ny, nx)
        wd_l = _stack(data, f"wind_direction_{lv}hPa", np.nan, ny, nx)
        z_l = gh - elev_nodes[None, :, :]
        u_l, v_l = _wind_components(ws_l, wd_l)
        # below (or too near) the previous level, e.g. under ground: carry that level up
        bad = ~np.isfinite(z_l) | ~np.isfinite(u_l) | ~np.isfinite(v_l) | (z_l < z_prev + 30.0)
        z_l = np.where(bad, z_prev + 30.0, z_l)
        u_l = np.where(bad, u_prev, u_l)
        v_l = np.where(bad, v_prev, v_l)
        k = len(used)
        fields[f"zl{k}"], fields[f"ul{k}"], fields[f"vl{k}"] = z_l, u_l, v_l
        used.append(f"{lv} hPa")
        z_prev, u_prev, v_prev = z_l, u_l, v_l
    return fields, used


def build_met(  # noqa: PLR0913 - mirrors the command-line options
    lat0: float,
    lon0: float,
    start: dt.datetime,
    hours: int,
    grid_n: int,
    constant_wind: tuple[float, float] | None,
    use_levels: bool = True,  # noqa: FBT001, FBT002 - positional in callers
    model: str | None = None,
    *,
    now: dt.datetime | None = None,
    extra: Sequence[str] = (),
) -> tuple[str, MetField, float | None]:
    """Hourly weather for the run as a :class:`MetField`.

    Fetches a ``grid_n`` x ``grid_n`` grid of Open-Meteo points sized to the distance
    the wind could carry the cloud, derives the stability class (Pasquill-Turner) and
    fills a missing mixing height with the class default. Without a level aloft, the
    10 m wind is extended to 100 m with the stability power law.

    Returns
    -------
    tuple
        Source description, the met field, and the ground elevation at the source (m).
    """
    t_first = start.replace(minute=0, second=0, microsecond=0)
    t_last = start + dt.timedelta(hours=hours + 1)
    if constant_wind is not None:
        met = _constant_wind_met(lat0, lon0, t_first, t_last, constant_wind)
        return "constant wind (user supplied)", met, None

    src, elev = _fetch_wind_grid(
        lat0,
        lon0,
        t_first,
        t_last,
        hours,
        grid_n,
        use_levels=use_levels,
        model=model,
        now=now,
        extra=extra,
    )
    data, name, z_up = src.data, src.name, src.z_up
    ny, nx = len(src.lat_nodes), len(src.lon_nodes)
    ws = _stack(data, "wind_speed_10m", 3.0, ny, nx)
    wd = _stack(data, "wind_direction_10m", 270.0, ny, nx)
    cloud = _stack(data, "cloud_cover", 50.0, ny, nx)
    sw = _stack(data, "shortwave_radiation", 0.0, ny, nx)
    precip = _stack(data, "precipitation", 0.0, ny, nx)
    extra_fields: dict[str, MetArray] = {}
    if all("temperature_2m" in d["hourly"] for d in data):
        extra_fields["t2"] = _stack(data, "temperature_2m", 15.0, ny, nx) + 273.15
    stab = stability_class(ws, sw, cloud)
    blh_default = DEFAULT_BLH[stab]
    blh = _stack(data, "boundary_layer_height", np.nan, ny, nx)
    blh = np.where(np.isnan(blh), blh_default, blh).clip(50.0, 4000.0)
    u, v = _wind_components(ws, wd)
    if z_up:
        ws_up = _stack(data, f"wind_speed_{z_up}m", np.nan, ny, nx)
        wd_up = _stack(data, f"wind_direction_{z_up}m", np.nan, ny, nx)
        fac = (z_up / 10.0) ** PROFILE_P[stab]
        ws_up = np.where(np.isnan(ws_up), ws * fac, ws_up)
        u_up, v_up = _wind_components(ws_up, np.where(np.isnan(wd_up), wd, wd_up))
    else:  # no level aloft: extend 10 m wind with the stability power law
        z_up = 100
        fac = (z_up / 10.0) ** PROFILE_P[stab]
        u_up, v_up = u * fac, v * fac
    _, i0 = _hour_index(data, t_first)
    fields: dict[str, MetArray] = {
        "u": u,
        "v": v,
        "u_up": u_up,
        "v_up": v_up,
        "ws": ws,
        "wd": wd,
        "cloud": cloud,
        "sw": sw,
        "precip": precip,
        "stab": stab,
        "blh": blh,
        **extra_fields,
    }
    level_fields, used = _pressure_level_fields(
        data, src.levels, (ny, nx), (np.full(u.shape, float(z_up)), u_up, v_up)
    )
    fields.update(level_fields)
    fields = {k: arr[i0:] for k, arr in fields.items()}
    if used:
        name += f", winds aloft on {len(used)} pressure levels"
    met = MetField(t_first, src.lat_nodes, src.lon_nodes, fields, float(z_up), len(used), used)
    return name, met, elev


def rotated_met(met: MetField, deg: float) -> MetField:
    """Copy of the met field with every wind vector turned clockwise by ``deg``.

    Wind FROM 180 becomes FROM 180 + deg. Used for the wind-direction ensemble.
    """
    c, s_ = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    f = dict(met.f)
    pairs = [("u", "v"), ("u_up", "v_up"), *[(f"ul{k}", f"vl{k}") for k in range(met.n_lev)]]
    for un, vn in pairs:
        f[un] = met.f[un] * c + met.f[vn] * s_
        f[vn] = -met.f[un] * s_ + met.f[vn] * c
    f["wd"] = (met.f["wd"] + deg) % 360
    return MetField(met.t0, met.lat_nodes, met.lon_nodes, f, met.z_up, met.n_lev, met.level_names)


def transport_wind(
    met: MetField,
    th: FloatArray,
    lat: FloatArray,
    lon: FloatArray,
    zt: FloatArray,
    cls: IntArray,
    blh: FloatArray,
) -> tuple[FloatArray, FloatArray]:
    """Wind (u, v) at transport height ``zt``.

    10 m to the level aloft (100, 120 or 80 m): blended on a log-height scale. Above that:
    linear interpolation through the pressure-level winds when the weather source has
    them (held constant above the top level); otherwise the stability power law, up to
    the mixing height.
    """
    u10 = met.sample("u", th, lat, lon)
    v10 = met.sample("v", th, lat, lon)
    uu = met.sample("u_up", th, lat, lon)
    vu = met.sample("v_up", th, lat, lon)
    z_up = met.z_up
    f = np.clip(np.log(np.maximum(zt, 10.0) / 10.0) / math.log(z_up / 10.0), 0.0, 1.0)
    u = u10 + f * (uu - u10)
    v = v10 + f * (vu - v10)
    if met.n_lev:
        zp, up, vp = np.full_like(zt, z_up), uu, vu
        for k in range(met.n_lev):
            zk = met.sample(f"zl{k}", th, lat, lon)
            uk = met.sample(f"ul{k}", th, lat, lon)
            vk = met.sample(f"vl{k}", th, lat, lon)
            g = np.clip((zt - zp) / np.maximum(zk - zp, 1.0), 0.0, 1.0)
            u = u + g * (uk - up)
            v = v + g * (vk - vp)
            zp, up, vp = zk, uk, vk
        return u, v
    above = np.clip(zt, z_up, np.maximum(blh, z_up)) / z_up
    scale = above ** PROFILE_P[cls]
    return u * scale, v * scale
