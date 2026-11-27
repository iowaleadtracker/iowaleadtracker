"""Turn a HYSPLIT run's output into the overlay file the site's maps read.

Usage (after the run, with its output dumped to text by HYSPLIT's ``con2asc -icdump -d -x``)::

    python make_overlay.py RUN_DIR overlay_0900.npz

RUN_DIR holds the run's ``CONTROL`` and the ``cdump_DDD_HH`` text files, one per hour. The
overlay keeps the two things the maps can show next to their own fields:

- ``air``: the hourly mean concentration in the 0-10 m layer (kg/m³), all particle sizes
  added, one array per hour;
- ``dep``: deposition on the ground since the release (kg/m²), at the end of each hour.

Both are for the whole release in ``CONTROL`` (``released_kg``); a map scales them to its
own case. HYSPLIT gives every vertical line source the full emission rate, so the values
are divided by the number of lines. The 0.003° output grid is averaged 2 x 2 to 0.006°,
about the size of the maps' own cells, which also evens out some of the particle noise,
and cut to the area the cloud reaches.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np

AIR_LEVEL, GROUND_LEVEL = "00010", "00000"  # the 0-10 m layer, and deposition
BLOCK = 2  # output cells averaged per overlay cell, each way
MARGIN = 4  # overlay cells kept around the cloud


def control(run: Path) -> dict[str, Any]:
    """Read the release time, the sources and the output grid from CONTROL."""
    lines = (run / "CONTROL").read_text(encoding="utf-8").split("\n")
    yy, mm, dd, hh, mi = (int(x) for x in lines[0].split())
    n_points = int(lines[1])
    n_met = int(lines[5 + n_points])
    k0 = 6 + n_points + 2 * n_met
    n_pol = int(lines[k0])
    released = sum(
        float(lines[k0 + 2 + 4 * p]) * float(lines[k0 + 3 + 4 * p]) for p in range(n_pol)
    )
    i = next(k for k, line in enumerate(lines) if line.strip() == "cdump")
    clat, clon = (float(x) for x in lines[i - 4].split())
    dx = float(lines[i - 3].split()[0])
    span_lat, span_lon = (float(x) for x in lines[i - 2].split())
    return {
        "start": f"20{yy:02d}-{mm:02d}-{dd:02d}T{hh:02d}:{mi:02d}",
        "hour0": hh,
        "lines": n_points // 2,  # each vertical line is two points, bottom and top
        "hours": int(lines[2 + n_points]),
        "released_kg": released,
        "dx": dx,
        "south": clat - span_lat / 2,
        "west": clon - span_lon / 2,
        "nlat": round(span_lat / dx) + 1,
        "nlon": round(span_lon / dx) + 1,
    }


def read_hours(run: Path, c: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    """Return air and cumulative deposition on the output grid, one array per hour."""
    nlat, nlon, hours = int(c["nlat"]), int(c["nlon"]), int(c["hours"])
    air = np.zeros((hours, nlat, nlon), dtype=np.float32)
    dep = np.zeros((hours, nlat, nlon), dtype=np.float32)
    total = np.zeros((nlat, nlon))
    files = sorted(run.glob("cdump_???_??"))
    if len(files) != hours:
        msg = f"expected {hours} hourly files in {run}, found {len(files)}"
        raise SystemExit(msg)
    for f in files:
        rows = f.read_text(encoding="utf-8").splitlines()
        head = [x.strip() for x in rows[0].split(",")]
        v = np.array([[float(x) for x in row.split(",")] for row in rows[1:]])
        ia = [k for k, name in enumerate(head) if name.endswith(AIR_LEVEL)]
        ig = [k for k, name in enumerate(head) if name.endswith(GROUND_LEVEL)]
        j = np.rint((v[:, 2] - c["south"]) / c["dx"]).astype(int)
        i = np.rint((v[:, 3] - c["west"]) / c["dx"]).astype(int)
        h = int(f.name[-2:]) - int(c["hour0"]) - 1  # the file is named for the hour's end
        air[h, j, i] = v[:, ia].sum(1) / c["lines"]
        np.add.at(total, (j, i), v[:, ig].sum(1) / c["lines"])
        dep[h] = total
    return air, dep


def coarsen(a: np.ndarray) -> np.ndarray:
    """Average BLOCK x BLOCK output cells (the last odd row and column are dropped)."""
    hours, nlat, nlon = a.shape
    nlat, nlon = nlat // BLOCK * BLOCK, nlon // BLOCK * BLOCK
    return (
        a[:, :nlat, :nlon]
        .reshape(hours, nlat // BLOCK, BLOCK, nlon // BLOCK, BLOCK)
        .mean(axis=(2, 4))
    )


def centers(first: float, dx: float, n: int) -> np.ndarray:
    """Return the middle of each averaged block: ``n`` of them, from the node at ``first``.

    Block ``b`` averages output nodes ``b * BLOCK`` to ``b * BLOCK + BLOCK - 1``, which are
    ``dx`` apart, so its middle is ``(BLOCK - 1) / 2`` nodes past its first node.
    """
    return np.asarray(first + (np.arange(n) * BLOCK + (BLOCK - 1) / 2) * dx)


def main(args: list[str]) -> None:
    """Write the overlay file."""
    run, out = Path(args[0]), Path(args[1])
    c = control(run)
    air, dep = (coarsen(a) for a in read_hours(run, c))
    step = c["dx"] * BLOCK
    lat = centers(c["south"], c["dx"], air.shape[1])
    lon = centers(c["west"], c["dx"], air.shape[2])
    used = (air.max(0) > 0) | (dep[-1] > 0)
    rows, cols = np.nonzero(used.any(1))[0], np.nonzero(used.any(0))[0]
    j0, j1 = max(rows[0] - MARGIN, 0), min(rows[-1] + MARGIN + 1, len(lat))
    i0, i1 = max(cols[0] - MARGIN, 0), min(cols[-1] + MARGIN + 1, len(lon))
    np.savez_compressed(
        out,
        lat=lat[j0:j1],
        lon=lon[i0:i1],
        air=air[:, j0:j1, i0:i1].astype(np.float32),
        dep=dep[:, j0:j1, i0:i1].astype(np.float32),
        released_kg=np.float64(c["released_kg"]),
        start_utc=np.array(c["start"]),
    )
    print(
        f"{out}: {air.shape[0]} hours, {j1 - j0} x {i1 - i0} cells of {step:g} deg, "
        f"{c['released_kg']:.1f} kg released from {int(c['lines'])} lines, "
        f"highest hourly mean {air.max() * 1e9:.0f} ug/m3"
    )


if __name__ == "__main__":
    main(sys.argv[1:])
