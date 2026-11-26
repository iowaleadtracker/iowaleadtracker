"""Download the public layers behind EPA's IAAAP Response Data Viewer as CSV.

Usage::

    python epa_fetch.py OUT_DIR

Writes ``epa_xact_public_viewer.csv`` (every record of the real-time "Xact" layer) and
``epa_air_stations.csv`` (the 43 sampling sites and the instruments EPA lists at each),
with distance and bearing from the plant added, and prints the download time (UTC).
The viewer is https://experience.arcgis.com/experience/1ddcf8b9d8314971b00dac8893ae9cd6,
linked from EPA's Nov. 25, 2026 news release. The data are EPA's preliminary real-time
values as posted; the layer does not name the substance or give a detection limit.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import math
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

SERVICES = "https://services.arcgis.com/cJ9YHowT8TU7DUyn/arcgis/rest/services"
XACT = f"{SERVICES}/IAAAP_Xact_Data_Public_Viewer/FeatureServer/0/query"
SITES = f"{SERVICES}/Air_Sampling_and_Monitoring_Location/FeatureServer/0/query"
LAT0, LON0 = 40.825518, -91.266502
KM_PER_DEG = 111.195
KM_PER_MI = 1.609344
PAGE = 1000


def dist_brg(lat: float, lon: float) -> tuple[float, int]:
    """Return miles and bearing (degrees from north) from the plant."""
    dy = (lat - LAT0) * KM_PER_DEG
    dx = (lon - LON0) * KM_PER_DEG * math.cos(math.radians(LAT0))
    return round(math.hypot(dx, dy) / KM_PER_MI, 1), round(
        (math.degrees(math.atan2(dx, dy)) + 360) % 360
    )


def query(url: str, **params: str) -> list[dict[str, Any]]:
    """Return every feature of a layer, paging through the service."""
    out: list[dict[str, Any]] = []
    while True:
        q = {"where": "1=1", "outFields": "*", "outSR": "4326", "f": "json", **params}
        q |= {"resultOffset": str(len(out)), "resultRecordCount": str(PAGE)}
        with urllib.request.urlopen(f"{url}?{urllib.parse.urlencode(q)}", timeout=60) as r:  # noqa: S310
            page = json.load(r).get("features", [])
        out += page
        if len(page) < PAGE:
            return out


def main(out: Path) -> None:
    """Download both layers and write the two CSV files."""
    out.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sites = query(SITES, orderByFields="Station_ID")
    with (out / "epa_air_stations.csv").open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(
            ["station_id", "instruments", "lat", "lon", "miles_from_plant", "bearing_from_plant"]
        )
        for ft in sites:
            a, g = ft["attributes"], ft["geometry"]
            w.writerow(
                [
                    a["Station_ID"],
                    a["Instrument_Type"],
                    round(g["y"], 5),
                    round(g["x"], 5),
                    *dist_brg(g["y"], g["x"]),
                ]
            )
    recs = [
        ft["attributes"] for ft in query(XACT, orderByFields="objectid", returnGeometry="false")
    ]
    recs.sort(key=lambda r: (r["Air_Station_ID"], r["Mon_Date_Time"], r["objectid"]))
    with (out / "epa_xact_public_viewer.csv").open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(
            [
                "station_id",
                "time_utc",
                "concentration",
                "units",
                "lat",
                "lon",
                "miles_from_plant",
                "bearing_from_plant",
                "objectid",
            ]
        )
        for r in recs:
            t = dt.datetime.fromtimestamp(r["Mon_Date_Time"] / 1000, dt.timezone.utc).strftime(
                "%Y-%m-%d %H:%M"
            )
            row = [
                r["Air_Station_ID"],
                t,
                r["Mon_Results"],
                r["Mon_Units"],
                r["Latitude"],
                r["Longitude"],
            ]
            w.writerow([*row, *dist_brg(r["Latitude"], r["Longitude"]), r["objectid"]])
    sys.stdout.write(f"downloaded {now}: {len(sites)} sites, {len(recs)} Xact records\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
