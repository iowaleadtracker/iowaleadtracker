"""Gridding puff records into hourly map fields, and the ensemble envelope smear."""

from __future__ import annotations

import math
from collections import deque
from typing import TYPE_CHECKING, cast

import numpy as np

from .dispersion import erf

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .types import FloatArray, Record


def cell_weights(edges: FloatArray, c: FloatArray, s: FloatArray) -> FloatArray:
    """Share of each 1-D Gaussian (center c, sd s) in each cell, divided by the cell width.

    Exact (difference of error functions) for narrow puffs; the density at the cell
    center for puffs wider than two cells.
    """
    d = edges[1] - edges[0]
    centers = 0.5 * (edges[1:] + edges[:-1])
    a = (edges[None, :] - c[:, None]) / (math.sqrt(2) * s[:, None])
    frac = 0.5 * np.diff(erf(a), axis=1)
    pdf = (
        np.exp(-0.5 * ((centers[None, :] - c[:, None]) / s[:, None]) ** 2)
        / (math.sqrt(2 * math.pi) * s[:, None])
        * d
    )
    out = np.where((s > 2 * d)[:, None], pdf, frac) / d
    result: FloatArray = np.where(out > 1e-300, out, 0.0)
    return result


def _map_window(
    records: Sequence[Record],
    n_cells: int,
    extent_m: float | None,
    domain_records: Sequence[Record] | None,
) -> tuple[FloatArray, FloatArray, float]:
    """Cell edges (x west->east, y north->south) and cell size for the map.

    A fixed square around the source with ``extent_m``; otherwise everything carrying
    mass, +/- 3 sigma, with 6 % padding.
    """
    if extent_m:  # fixed square window centered on the source
        x0, x1, y0, y1 = -extent_m, extent_m, -extent_m, extent_m
        pad = 1.0
    else:  # everything carrying mass, +/- 3 sigma
        xs, ys = [0.0], [0.0]
        for _, x, y, sy, w, dep, _inv, _last in domain_records or records:
            keep = (w + dep) > 0
            if keep.any():
                xs += [float(np.min((x - 3 * sy)[keep])), float(np.max((x + 3 * sy)[keep]))]
                ys += [float(np.min((y - 3 * sy)[keep])), float(np.max((y + 3 * sy)[keep]))]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        pad = 1.06
    span = max(x1 - x0, y1 - y0, 2000.0) * pad
    cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
    dx = span / n_cells
    nx = max(2, math.ceil(max(x1 - x0, 2000.0) * pad / dx - 1e-9))
    ny = max(2, math.ceil(max(y1 - y0, 2000.0) * pad / dx - 1e-9))
    xe = cx - nx * dx / 2 + dx * np.arange(nx + 1)
    ye = cy + ny * dx / 2 - dx * np.arange(ny + 1)  # north -> south
    return cast("FloatArray", xe), cast("FloatArray", ye), dx


def _accumulate_step(
    xe: FloatArray,
    ye: FloatArray,
    record: Record,
    cum: FloatArray,
    cum_n: FloatArray,
    *,
    counts: bool,
) -> tuple[FloatArray, FloatArray]:
    """Grid one time step: return its air fields (mass, count); add deposition to the totals.

    Puffs are spread in chunks of 4000 to bound memory. Deposition goes straight into
    ``cum`` and ``cum_n`` chunk by chunk.
    """
    _, x, y, s, wc, wd, inv, _ = record
    ny, nx = len(ye) - 1, len(xe) - 1
    step_c = np.zeros((ny, nx))
    step_n = np.zeros((ny, nx))
    for lo in range(0, len(x), 4000):
        sl = slice(lo, lo + 4000)
        gx = cell_weights(xe, x[sl], s[sl])  # (P, nx)
        gy = cell_weights(ye[::-1], y[sl], s[sl])[:, ::-1]  # (P, ny) north first
        step_c += (gy * wc[sl, None]).T @ gx  # kg s/m3 this step
        cum += (gy * wd[sl, None]).T @ gx
        if counts:
            step_n += (gy * (wc * inv)[sl, None]).T @ gx
            cum_n += (gy * (wd * inv)[sl, None]).T @ gx
    return step_c, step_n


def _add_step(
    F: dict[str, FloatArray],
    h: int,
    step: tuple[FloatArray, FloatArray],
    dt_s: float,
    *,
    last: bool,
    counts: bool,
) -> None:
    """Add one step to hour ``h``: hourly sum, in-hour peak, and the end-of-hour field."""
    step_c, step_n = step
    F["conc"][h] += step_c
    np.maximum(F["peak"][h], step_c / dt_s, out=F["peak"][h])
    if counts:
        F["conc_n"][h] += step_n
        np.maximum(F["peak_n"][h], step_n / dt_s, out=F["peak_n"][h])
    if last:  # the cloud as it stands at the hour's end
        F["snap"][h] = step_c / dt_s
        if counts:
            F["snap_n"][h] = step_n / dt_s


def grid_fields(
    records: Sequence[Record],
    n_hours: int,
    n_cells: int,
    dt_s: float,
    extent_m: float | None = None,
    domain_records: Sequence[Record] | None = None,
    *,
    counts: bool = True,
) -> tuple[dict[str, FloatArray], tuple[FloatArray, FloatArray, float]]:
    """Grid the puff records into hourly map fields.

    Fields (hours, ny, nx): ``conc`` hourly-mean and ``peak`` in-hour peak ground-level
    concentration (kg/m3), ``snap`` the field at the end of each hour, ``dep``
    cumulative deposition (kg/m2), and ``m60`` the highest running 60-minute mean
    reached during each hour (the averaging time of AEGL/PAC style levels of concern,
    as used for ALOHA threat zones). With ``counts`` the first four also come by
    particle count (``conc_n``, ``peak_n``, ``snap_n``, ``dep_n``). ``domain_records``
    sets the map window from another (larger) set of records, e.g. all ensemble
    members.

    Returns
    -------
    tuple
        The fields, and (x cell edges, y cell edges, cell size) in m from the source.
    """
    xe, ye, dx = _map_window(records, n_cells, extent_m, domain_records)
    ny, nx = len(ye) - 1, len(xe) - 1
    names = ["conc", "peak", "snap", "dep", "m60"]
    if counts:
        names += ["conc_n", "peak_n", "snap_n", "dep_n"]
    F = {k: np.zeros((n_hours, ny, nx)) for k in names}
    win_len = round(3600 / dt_s)
    window: deque[FloatArray] = deque()
    run_sum = np.zeros((ny, nx))
    cum = np.zeros((ny, nx))
    cum_n = np.zeros((ny, nx))
    h_prev = 0
    for record in records:  # one record per model time step
        hour, last = record[0], record[7]
        h = min(hour, n_hours - 1)
        while h_prev < h:  # close out finished hours
            F["dep"][h_prev] = cum
            if counts:
                F["dep_n"][h_prev] = cum_n
            h_prev += 1
        step_c, step_n = _accumulate_step(xe, ye, record, cum, cum_n, counts=counts)
        _add_step(F, h, (step_c, step_n), dt_s, last=last, counts=counts)
        window.append(step_c)
        run_sum += step_c
        if len(window) > win_len:
            run_sum -= window.popleft()
        np.maximum(F["m60"][h], run_sum / 3600.0, out=F["m60"][h])
    while h_prev < n_hours:
        F["dep"][h_prev] = cum
        if counts:
            F["dep_n"][h_prev] = cum_n
        h_prev += 1
    F["conc"] /= 3600.0  # kg s/m3 -> hourly-mean kg/m3
    if counts:
        F["conc_n"] /= 3600.0
    return F, (xe, ye, dx)


def angular_smear(arr: FloatArray, xe: FloatArray, ye: FloatArray, half_deg: float) -> FloatArray:
    """Highest value of each field (hours, ny, nx) over rotations about the source.

    Rotations span +/- ``half_deg``. Fills the gaps between neighbouring ensemble
    members.
    """
    dx = xe[1] - xe[0]
    nx, ny = len(xe) - 1, len(ye) - 1
    X, Y = np.meshgrid(0.5 * (xe[1:] + xe[:-1]), 0.5 * (ye[1:] + ye[:-1]))
    rmax = float(np.hypot(X, Y).max())
    n = int(min(max(math.ceil(math.radians(2 * half_deg) * rmax / dx), 2), 60)) | 1
    out: FloatArray = arr.copy()
    flat = arr.reshape(arr.shape[0], -1)
    for d in np.linspace(-half_deg, half_deg, n):
        if abs(d) < 1e-12:
            continue
        c, s_ = math.cos(math.radians(d)), math.sin(math.radians(d))
        i = np.floor((X * c - Y * s_ - xe[0]) / dx).astype(int)
        j = np.floor((ye[0] - (X * s_ + Y * c)) / dx).astype(int)
        ok = (i >= 0) & (i < nx) & (j >= 0) & (j < ny)
        idx = np.where(ok, j * nx + i, 0).ravel()
        np.maximum(out, flat[:, idx].reshape(arr.shape) * ok, out=out)
    return out
