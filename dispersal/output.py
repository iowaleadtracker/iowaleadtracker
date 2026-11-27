"""Page output: packed fields, the HYSPLIT cross-check files and the HTML map."""

from __future__ import annotations

import base64
import datetime as dt
import json
import math
import zlib
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import argparse
    from collections.abc import Sequence

    from .types import FloatArray, Json


def pack(arr: FloatArray, decades: int = 9) -> Json:
    """Encode a field for the page: log10-quantised to uint8, zlib-compressed, base64.

    Level 0 means below ``max / 10**decades``; levels 1-255 span the ``decades``
    decades below the maximum. Returns ``hi`` and ``lo`` (log10 bounds), ``max`` and
    ``data``.
    """
    vmax = float(np.max(arr))
    if vmax <= 0:
        return {
            "hi": 0.0,
            "lo": -1.0,
            "data": base64.b64encode(
                zlib.compress(np.zeros(arr.size, np.uint8).tobytes(), 9)
            ).decode(),
            "max": 0.0,
        }
    hi = math.log10(vmax)
    lo = hi - decades
    with np.errstate(divide="ignore"):
        lv = np.log10(np.where(arr > 0, arr, 1e-300))
    q = np.where(lv >= lo, np.round((lv - lo) / (hi - lo) * 254) + 1, 0).astype(np.uint8)
    return {
        "hi": hi,
        "lo": lo,
        "max": vmax,
        "data": base64.b64encode(zlib.compress(q.tobytes(), 9)).decode(),
    }


MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def gdas1_files(start: dt.datetime, hours: int) -> list[str]:
    """NOAA ARL GDAS1 (1 degree) archive files covering the run: ``gdas1.mmmyy.wN``."""
    names, t = [], start
    end = start + dt.timedelta(hours=hours)
    while t <= end + dt.timedelta(days=1):
        week = min((t.day - 1) // 7 + 1, 5)
        n = f"gdas1.{MONTHS[t.month - 1]}{t.year % 100:02d}.w{week}"
        if n not in names:
            names.append(n)
        t += dt.timedelta(days=1)
    return names


def hysplit_overlay(
    path: str | Path,
    start: dt.datetime,
    hours: int,
    release_kg: float,
    centers: tuple[FloatArray, FloatArray],
) -> tuple[dict[str, FloatArray], Json]:
    """Put a saved NOAA HYSPLIT run on the map's grid, scaled to this run's release.

    ``path`` is a file made by a scenario's ``make_overlay.py``: HYSPLIT's hourly mean air
    concentration near the ground and its deposition since the release, on a latitude and
    longitude grid, for a stated mass released at a stated time. HYSPLIT's results scale
    with the mass released, so they are multiplied by ``release_kg`` over the file's mass,
    then read at the map's cell centers (``centers``: latitudes and longitudes of the rows
    and columns) by interpolating between HYSPLIT's cells.

    Returns
    -------
    tuple
        The fields ``hy_conc`` and ``hy_dep``, shaped like the map's own (hour, row,
        column), and a note for the page: the mass ratio used, the file's name, and each
        hour's highest value on the map (``airMax``, ``depMax``).

    Raises
    ------
    ValueError
        If the file is for another release time or covers fewer hours than the run.
    """
    with np.load(path) as z:
        lat, lon, air, dep = z["lat"], z["lon"], z["air"], z["dep"]
        file_start, file_kg = str(z["start_utc"]), float(z["released_kg"])
    want = start.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M")
    if file_start != want:
        msg = f"the HYSPLIT overlay is for a release at {file_start} UTC, not {want} UTC"
        raise ValueError(msg)
    if air.shape[0] < hours:
        msg = f"the HYSPLIT overlay covers {air.shape[0]} hours, fewer than the run's {hours}"
        raise ValueError(msg)
    rows, cols = centers
    # position of each map row and column on HYSPLIT's grid, in cells; outside it, nothing
    fj = (rows - lat[0]) / (lat[1] - lat[0])
    fi = (cols - lon[0]) / (lon[1] - lon[0])
    inside = ((fj >= 0) & (fj <= len(lat) - 1))[:, None] & ((fi >= 0) & (fi <= len(lon) - 1))
    j0 = np.clip(np.floor(fj).astype(int), 0, len(lat) - 2)
    i0 = np.clip(np.floor(fi).astype(int), 0, len(lon) - 2)
    wj = np.clip(fj - j0, 0.0, 1.0)[:, None]
    wi = np.clip(fi - i0, 0.0, 1.0)[None, :]

    def on_map(field: FloatArray) -> FloatArray:
        a = field[:hours].astype(float)
        top = a[:, j0][:, :, i0] * (1 - wi) + a[:, j0][:, :, i0 + 1] * wi
        bottom = a[:, j0 + 1][:, :, i0] * (1 - wi) + a[:, j0 + 1][:, :, i0 + 1] * wi
        return np.where(inside, top * (1 - wj) + bottom * wj, 0.0) * (release_kg / file_kg)

    fields = {"hy_conc": on_map(air), "hy_dep": on_map(dep)}
    note = {
        "file": Path(path).name,
        "scaledBy": release_kg / file_kg,
        "releasedKg": file_kg,
        "airMax": [float(v) for v in fields["hy_conc"].max(axis=(1, 2))],
        "depMax": [float(v) for v in fields["hy_dep"].max(axis=(1, 2))],
    }
    return fields, note


def hysplit_files(a: argparse.Namespace, bins: Sequence[Json], grid: Json) -> dict[str, str]:
    """CONTROL and SETUP.CFG for an equivalent NOAA HYSPLIT concentration run.

    The source is a vertical line (two starting heights at one location) for an
    explosion, or a point at ``--release-height`` otherwise; one pollutant per
    particle-size bin with gravitational settling from diameter and density.
    Mass units are kg, so HYSPLIT concentrations come out in kg/m3.

    References
    ----------
    Stein et al. (2015), NOAA's HYSPLIT modeling system.
    """
    t = a.start
    if a.explosion:
        heights = [10.0, round(a.explosion["cloudTop"], 1)]
        duration = 0.1  # h; ~cloud stabilisation time for a detonation
    else:
        heights = [a.release_height]
        duration = max(a.release_duration, 0.1)
    met = gdas1_files(t, a.hours)
    dlat = max(round(grid["dx"] / 111195.0, 3), 0.001)
    span_lat = round(grid["north"] - grid["south"], 2) + 2 * dlat
    span_lon = round(grid["east"] - grid["west"], 2) + 2 * dlat
    lines = [t.strftime("%y %m %d %H %M"), str(len(heights))]
    lines += [f"{a.lat:.4f} {a.lon:.4f} {h:.1f}" for h in heights]
    lines += [str(a.hours), "0", "10000.0", str(len(met))]
    for m in met:
        lines += ["./", m]
    lines.append(str(len(bins)))
    for k, b in enumerate(bins):
        mass = a.release_mass * b["frac"]
        lines += [f"P{k + 1:03d}", f"{mass / duration:.6g}", f"{duration:g}", "00 00 00 00 00"]
    lines += [
        "1",
        f"{(grid['north'] + grid['south']) / 2:.4f} {(grid['east'] + grid['west']) / 2:.4f}",
        f"{dlat:g} {dlat:g}",
        f"{span_lat:g} {span_lon:g}",
        "./",
        "cdump",
        "1",
        "100",
        "00 00 00 00 00",
        "00 00 00 00 00",
        "00 01 00",
        str(len(bins)),
    ]
    for b in bins:
        lines += [
            f"{b['d'] * 1e6:.3g} {b.get('rho', a.density) / 1000:.3g} 1.0",
            "0.0 0.0 0.0 0.0 0.0",  # settling computed from size/density
            "0.0 4.0E+04 5.0E-06",  # HYSPLIT's usual particle wet removal
            "0.0",
            "0.0",
        ]
    control = "\n".join(lines) + "\n"
    setup = "&SETUP\n initd = 0,\n numpar = 50000,\n maxpar = 100000,\n/\n"
    notes = (
        "HYSPLIT cross-check for this scenario\n"
        f"Meteorology for past dates: download {', '.join(met)} from "
        "https://www.ready.noaa.gov/data/archives/gdas1/ into this folder (or a finer ARL "
        "archive such as gfs0p25, nam12 or hrrr, and edit CONTROL's met lines). Archive files "
        "exist only after the fact; for a forecast, use NOAA ARL forecast meteorology "
        "(https://www.ready.noaa.gov/data/forecast/) and set CONTROL's met lines to it.\n"
        "Run: hycs_std   (reads CONTROL and SETUP.CFG here, writes cdump)\n"
        "Output: concentration in kg/m3 averaged over 0-100 m, hourly; deposition in kg/m2.\n"
        "Online alternative: NOAA READY HYSPLIT (ready.noaa.gov) with the same start, "
        "location, heights and particle sizes.\n"
    )
    return {"CONTROL": control, "SETUP.CFG": setup, "README.txt": notes}


TEMPLATE = Path(__file__).resolve().parents[1] / "template.html"


def load_template() -> str:
    """Read the interactive map page that the data is embedded into."""
    return TEMPLATE.read_text(encoding="utf-8")


def write_html(payload: Json, out: str | Path) -> int:
    """Write the self-contained map page; returns its size in characters.

    Keys starting with ``_`` are left out. The JSON is escaped so that no string in it
    can close the ``<script>`` element it sits in.
    """
    data = {k: v for k, v in payload.items() if not k.startswith("_")}
    # Escape <, >, & and line separators so no string in the data can close the <script>.
    blob = (
        json.dumps(data, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
    html = load_template().replace("/*__DATA__*/null", blob, 1)
    Path(out).write_text(html, encoding="utf-8")
    return len(html)
