"""Save the modeled lead on the ground for the brief's "What is needed now" section.

Usage::

    python ground_fields.py MAP.html OVERLAY.npz

``MAP.html`` is the site's archived-weather map for the Low case
(``outputs/site/maps/archived-low-0900.html`` after ``make_map_picker.py --build``).
``OVERLAY.npz`` is the saved HYSPLIT run for the same blast (``overlay_0900.npz``, made by
the scenario's ``hysplit-archived/make_overlay.py``), which is for all of the lead and is
scaled here to the Low case.

Writes ``data/ground_fields.npz``: lead on the ground eight hours after the blast, in
kg/m2, for the lowest published case (7% of the lead airborne as fine dust), from the two
models, cut to where either has 0.1 µg/ft2 or more. ``brief.py`` reads it.
"""

from __future__ import annotations

import base64
import json
import sys
import zlib
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
LOW_CASE = 0.07  # share of the lead airborne as fine dust in the lowest published case
UG_FT2 = 1e9 * 0.09290304  # kg/m2 to µg/ft2
KEEP = 0.1 / UG_FT2  # cut to where a field has this much or more


def tracker(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return latitudes, longitudes and the last hour's deposition from a built map page."""
    text = path.read_text(encoding="utf-8")
    start = text.index("const DATA = ") + len("const DATA = ")
    data = json.JSONDecoder().raw_decode(text[start:])[0]
    share = data["meta"]["explosionOpts"]["airborneFraction"]
    if abs(share - LOW_CASE) > 1e-9:
        raise SystemExit(f"{path.name} is for {share:.0%} airborne, not the Low case")
    g, p = data["grid"], data["grid"]["dep"]
    q = np.frombuffer(zlib.decompress(base64.b64decode(p["data"])), np.uint8)
    q = q.reshape(-1, g["ny"], g["nx"])[-1].astype(float)
    dep = np.where(q > 0, 10 ** (p["lo"] + (q - 1) / 254 * (p["hi"] - p["lo"])), 0.0)
    lat = g["north"] - (np.arange(g["ny"]) + 0.5) * (g["north"] - g["south"]) / g["ny"]
    lon = g["west"] + (np.arange(g["nx"]) + 0.5) * (g["east"] - g["west"]) / g["nx"]
    return lat[::-1], lon, dep[::-1]  # south to north, like the other fields here


def hysplit(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return latitudes, longitudes and the last hour's deposition, scaled to the Low case."""
    with np.load(path) as z:
        return z["lat"], z["lon"], z["dep"][-1].astype(float) * LOW_CASE


def cut(lat: np.ndarray, lon: np.ndarray, dep: np.ndarray) -> dict[str, np.ndarray]:
    """Keep the rows and columns that hold ``KEEP`` or more, with one cell around them."""
    rows, cols = np.nonzero((dep >= KEEP).any(axis=1))[0], np.nonzero((dep >= KEEP).any(axis=0))[0]
    r = slice(max(rows[0] - 1, 0), rows[-1] + 2)
    c = slice(max(cols[0] - 1, 0), cols[-1] + 2)
    return {"lat": lat[r], "lon": lon[c], "dep": dep[r, c].astype(np.float32)}


def main(args: list[str]) -> None:
    """Write ``data/ground_fields.npz`` from a built map and the saved HYSPLIT run."""
    fields = {"tracker": cut(*tracker(Path(args[0]))), "hysplit": cut(*hysplit(Path(args[1])))}
    out: dict[str, Any] = {f"{k}_{n}": v for k, f in fields.items() for n, v in f.items()}
    np.savez_compressed(HERE / "data" / "ground_fields.npz", **out)
    for k, f in fields.items():
        print(f"{k}: {f['dep'].shape}, highest {float(np.max(f['dep'])) * UG_FT2:.0f} µg/ft2")


if __name__ == "__main__":
    main(sys.argv[1:])
