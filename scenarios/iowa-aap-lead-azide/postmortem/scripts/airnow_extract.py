"""Extract PM2.5, PM10 and wind near the plant from EPA AirNow's public hourly files.

Usage::

    python airnow_extract.py OUT.csv [FIRST_HOUR_UTC LAST_HOUR_UTC]

Downloads ``Monitoring_Site_Locations_V2.dat`` and ``HourlyData_2026112500..23.dat`` from
https://files.airnowtech.org/airnow/2026/20261125/ and keeps the monitors within 160 miles
of the plant. Hours are hour-beginning, UTC. AirNow's real-time data are preliminary.
"""

from __future__ import annotations

import csv
import io
import math
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://files.airnowtech.org/airnow/2026/20261125"
LAT0, LON0 = 40.825518, -91.266502
KM_PER_DEG, KM_PER_MI = 111.195, 1.609344
RADIUS_MI = 160
KEEP = {"PM2.5", "PM10", "RWD", "RWS"}
SITE_COLUMNS = 20
HOUR_COLUMNS = 9


def fetch(name: str) -> str | None:
    """Return one AirNow file as text, or None if it isn't posted yet."""
    try:
        with urllib.request.urlopen(f"{BASE}/{name}", timeout=60) as r:  # noqa: S310
            return str(r.read().decode("latin-1"))
    except urllib.error.HTTPError:
        return None


def main(out: Path, first: int, last: int) -> None:
    """Write the nearby monitors' hourly values to ``out``."""
    sites: dict[str, tuple[str, str, float, float, int, int]] = {}
    for r in csv.reader(
        io.StringIO(fetch("Monitoring_Site_Locations_V2.dat") or ""), delimiter="|"
    ):
        if len(r) < SITE_COLUMNS or r[0] == "StationID":
            continue
        try:
            la, lo = float(r[11]), float(r[12])
        except ValueError:
            continue
        dy = (la - LAT0) * KM_PER_DEG
        dx = (lo - LON0) * KM_PER_DEG * math.cos(math.radians(LAT0))
        mi = math.hypot(dx, dy) / KM_PER_MI
        if mi < RADIUS_MI:
            sites.setdefault(
                r[1],
                (
                    r[6],
                    r[19],
                    la,
                    lo,
                    round(mi),
                    round((math.degrees(math.atan2(dx, dy)) + 360) % 360),
                ),
            )
    head = [
        "aqsid",
        "site",
        "state",
        "lat",
        "lon",
        "miles_from_plant",
        "bearing",
        "parameter",
        "date",
    ]
    head += ["hour_utc_beginning", "value", "units", "source"]
    with out.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(head)
        for hour in range(first, last + 1):
            text = fetch(f"HourlyData_20261125{hour:02d}.dat")
            if text is None:
                continue
            for r in csv.reader(io.StringIO(text), delimiter="|"):
                if len(r) >= HOUR_COLUMNS and r[2] in sites and r[5] in KEEP:
                    name, state, la, lo, mi, brg = sites[r[2]]
                    w.writerow(
                        [
                            r[2],
                            name,
                            state,
                            la,
                            lo,
                            mi,
                            brg,
                            r[5],
                            r[0],
                            r[1],
                            r[7],
                            r[6],
                            r[8].strip(),
                        ]
                    )


if __name__ == "__main__":
    a = sys.argv[1:]
    main(Path(a[0]), int(a[1]) if len(a) > 1 else 11, int(a[2]) if len(a) > 2 else 23)
