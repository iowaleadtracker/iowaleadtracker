"""Save EPA's public sampling sites and lead readings for the map (``epa_sites.json``).

Usage::

    python3 tools/refresh_epa.py            # downloads; needs the network
    python3 tools/refresh_epa.py --check    # prints what changed, writes nothing

It reads three public layers behind EPA's Iowa Army Ammunition Plant response data viewer
(the brief's ``epa_fetch.py`` reads two of them): the air sampling sites and the
instruments EPA lists at each, the real-time readings of the four continuous lead monitors
(Xact, AS01 to AS04), and the soil sampling locations. It writes
``scenarios/iowa-aap-lead-azide/epa_sites.json``, which the site build hands to the map as
``--reference-sites``. Refreshing it is a deliberate step, like the saved forecasts: the
file is the record of what EPA had posted when it was pulled, and a build with it makes
the same maps on any machine.

The values are EPA's preliminary data as posted. The lead layer does not name the
substance or give a detection limit; EPA calls the stations "Xact stations monitoring for
lead" (the brief's EPA 2026b). No other site has posted results.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SCENARIO = ROOT / "scenarios" / "iowa-aap-lead-azide"
BRIEF = SCENARIO / "postmortem" / "monitor-placement-brief"
OUT = SCENARIO / "epa_sites.json"
UTC = dt.timezone.utc
# The plant point the site uses (as epa_fetch.py), for distances.
LAT0, LON0 = 40.825518, -91.266502
#: The detonation, 9 a.m. CST Nov. 25, 2026 (as the brief's RELEASE_UTC): readings at or
#: after it are "since the blast", earlier ones are the baseline.
EVENT = dt.datetime(2026, 11, 25, 15, 0, tzinfo=UTC)
# EPA's original viewer (cited in works_cited.py) now only shows this newer app inside it,
# "Iowa Army Ammunition Plant Response Sample Data Viewer", so links go to the newer one.
VIEWER = "https://experience.arcgis.com/experience/00329268edc24f068127d26200d35a45"
VIEWER_ITEM = "https://www.arcgis.com/sharing/rest/content/items/00329268edc24f068127d26200d35a45"
# The viewer's data source for the Xact lead layer. A link with ?data_filter=<this>:<where>
# opens the viewer with that layer filtered to one station (Experience Builder's URL
# parameters). download() checks the viewer still has it, since EPA rebuilds its apps.
XACT_SOURCE = "dataSource_1-1a214a59c41-layer-7"


def viewer_link(station_id: str) -> str:
    """Return EPA's viewer with its lead layer filtered to one station, as EPA spells it."""
    where = urllib.parse.quote(f"Air_Station_ID='{station_id}'", safe="")
    return f"{VIEWER}/?data_filter={XACT_SOURCE}:{where}"


def check_viewer() -> None:
    """Stop if EPA's viewer no longer has the Xact data source the links filter."""
    with urllib.request.urlopen(f"{VIEWER_ITEM}/data?f=json", timeout=60) as r:  # noqa: S310
        app = json.load(r)
    used = {
        u.get("dataSourceId")
        for w in app.get("widgets", {}).values()
        for u in (w.get("useDataSources") or [])
    }
    if XACT_SOURCE not in used:
        msg = f"EPA's viewer no longer uses {XACT_SOURCE}; find its Xact layer's id again"
        raise SystemExit(msg)


BRIEF_URL = "https://iowaleadtracker.com/monitor-placement/"

#: What each instrument is, for the map's detail view, with the symbol beside its results
#: (the shape of the kind of site it stands for; the Summa canister, which stands for none,
#: a circle); whether it has posted results is
#: shown from the data (``readings``), not written here. Keep these to what the sources say,
#: and don't say what an instrument can't measure unless its source says so:
#: Xact and the air cassette from the monitor-placement brief (EPA 2026a, 2026b there);
#: DustTrak from TSI's DustTrak II 8530 page, AreaRAE from Honeywell's AreaRAE Pro RAEMet
#: sensor page, the Summa canister from EPA Compendium Method TO-15 (EPA/625/R-96/010b,
#: 1999). All three are in works_cited.py (checked 28 November 2026).
#: The detection limit shown beside lead-in-air results: the only one published, the
#: Army's, from the legend of its 3 p.m. air map ("0.18 ug/m3 - Lead Air Sampling Method
#: Detection Limit"; McFate 2026d in works_cited.py). It is for the Army's sampling method;
#: EPA hasn't published the Xact monitors' own.
AIR_LIMIT = {
    "v": 0.18,
    "unit": "µg/m³",
    "label": "the Army's lead air sampling method, from its 3 p.m. maps of Nov. 25 (McFate 2026d)",
    # the site's Methodology and References, where McFate 2026d is listed: a path on the
    # site, so the mirror and local builds open their own copy
    "url": "/#references",
}
INSTRUMENTS: dict[str, dict[str, Any]] = {
    "xact": {
        "name": "Xact continuous lead monitor",
        "shape": "diamond",
        "limit": AIR_LIMIT,
        "text": "Collects particles from the air on a filter tape and measures their metals "
        "by X-ray fluorescence as it runs, so its readings post without a lab. EPA "
        "hasn't published the model, inlet size or detection limit.",
    },
    "cassette": {
        "name": "Air cassette",
        "shape": "square",
        "limit": AIR_LIMIT,
        "text": "A filter that collects particles from the air. A lab measures the lead on it.",
    },
    "dusttrak": {
        "name": "DustTrak",
        "shape": "square-dot",
        "text": "A light-scattering laser photometer that gives real-time readings of the "
        "mass of particles in the air (TSI).",
    },
    "arearae": {
        "name": "AreaRAE",
        "shape": "square-dot",
        "text": "A wireless monitor for up to seven hazards, including gamma radiation, "
        "volatile organic compounds, combustible and toxic gases, and oxygen (Honeywell).",
    },
    "summa": {
        "name": "Summa canister",
        "text": "A specially prepared stainless steel canister that takes in a sample of "
        "air for a lab to test for volatile organic compounds (EPA Method TO-15).",
    },
    "water": {
        "name": "Water sample",
        "shape": "circle",
        "text": "EPA lists where and when it started sampling water.",
    },
    "soil": {
        "name": "Soil sample",
        "shape": "triangle",
        "text": "EPA lists where and when it started sampling soil.",
    },
}
#: EPA's spellings in ``Instrument_Type``.
ALIASES = {
    "dust trak": "dusttrak",
    "dusttrak": "dusttrak",
    "arearae": "arearae",
    "air cassette": "cassette",
    "summa cannister": "summa",
    "summa canister": "summa",
}
#: One symbol per kind of site, by what it can say about lead. No common standard exists
#: for these; the diamond and square follow the monitor-placement brief's map. A site's
#: details describe the kind's own instrument (the sample that says something about lead)
#: and only name the other instruments there.
#:
#: "fill" is the color a site's symbol is filled with once results have been posted from
#: it since the blast (until then it is outlined): the colors EPA's own map uses for each
#: layer (its web map 4ac8e3f8e6f94a209292e5992aba5d5f, read Nov. 28, 2026). EPA colors
#: each lead reading by one break, 32 µg/m³: "breaks" fill a monitor by its highest result
#: since the blast, in the color of the first break it is below, else the last.
KINDS: dict[str, dict[str, Any]] = {
    "lead": {
        "label": "Continuous lead monitor (Xact)",
        "shape": "diamond",
        "instrument": "xact",
        "fill": {
            "breaks": [
                {"below": 32, "color": "#59ff00", "label": "below 32 µg/m³"},
                {"color": "#ffee00", "label": "32 µg/m³ or more"},
            ]
        },
    },
    "realtime": {
        "label": "Air filter, with dust and gas monitors",
        "shape": "square-dot",
        "instrument": "cassette",
        "fill": {"color": "#149ece"},
    },
    "filter": {
        "label": "Air filter and gas canister",
        "shape": "square",
        "instrument": "cassette",
        "fill": {"color": "#e500ff"},
    },
    "soil": {
        "label": "Soil sampling location",
        "shape": "triangle",
        "instrument": "soil",
        "fill": {"color": "#966400"},
    },
    # EPA's own map draws its water sites as circles too
    "water": {
        "label": "Water sampling location",
        "shape": "circle",
        "instrument": "water",
        "fill": {"color": "#0000ff"},
    },
}
NOTE = (
    "EPA's preliminary data as posted, saved {when}. Only the four continuous lead "
    "monitors post results. A reading near zero doesn't show whether a cloud missed the "
    "monitor or little lead got out. Measurements, not model estimates."
)


def iso(ms: float) -> str:
    """Return an ESRI time (ms since 1970, UTC) as ``YYYY-MM-DDTHH:MMZ``."""
    return dt.datetime.fromtimestamp(ms / 1000, UTC).strftime("%Y-%m-%dT%H:%MZ")


def station(sid: str) -> str:
    """Return EPA's station ID without its hyphen: the two layers spell them differently."""
    return sid.replace("-", "").strip().upper()


def instrument_keys(text: str) -> list[str]:
    """Return the instruments named in an ``Instrument_Type``, as keys of INSTRUMENTS."""
    out = []
    for part in text.split(","):
        word = part.strip()
        key = ALIASES.get(word.lower())
        if key and key not in out:
            out.append(key)
        elif not key and word:
            raise ValueError(f"unknown instrument {word!r}: add it to ALIASES and INSTRUMENTS")
    return out


def summarize_readings(recs: list[dict[str, Any]], unit: str) -> dict[str, Any]:
    """Summarize one instrument's results: since the blast, before it, and the last one."""
    # a record without a time or a value is not a measurement: left out
    rows = sorted(
        (r["Mon_Date_Time"], float(r["Mon_Results"]))
        for r in recs
        if r.get("Mon_Date_Time") is not None and r.get("Mon_Results") is not None
    )
    if not rows:
        msg = "a station has records but no measurements"
        raise ValueError(msg)
    event_ms = EVENT.timestamp() * 1000
    after = [(t, v) for t, v in rows if t >= event_ms]
    before = [(t, v) for t, v in rows if t < event_ms]

    def peak(rs: list[tuple[float, float]]) -> dict[str, Any] | None:
        if not rs:
            return None
        t, v = max(rs, key=lambda r: (r[1], -r[0]))  # the first time it reached the highest
        return {"v": v, "t": iso(t)}

    t_last, v_last = rows[-1]
    return {
        "unit": unit,
        "posted": len(after),
        "zero": sum(v == 0 for _, v in after),
        "max": peak(after),
        "maxBefore": peak(before),
        "first": iso(rows[0][0]),
        "last": {"v": v_last, "t": iso(t_last)},
    }


#: Sample locations farther than this from the plant are left out: EPA's water layer puts
#: five samples at one point in the Atlantic, about 960 miles away, which can't be a site
#: of this response. download() reports how many were left out.
MAX_MILES = 300.0


def miles_from_plant(lat: float, lon: float) -> float:
    """Return the distance from the plant point the site uses, in miles."""
    dy = (lat - LAT0) * 111.195
    dx = (lon - LON0) * 111.195 * math.cos(math.radians(LAT0))
    return math.hypot(dx, dy) / 1.609344


def sample_spots(features: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    """Return one site per spot for a layer of sample locations with start times.

    EPA lists some spots several times, with different start times; each spot is one
    place on the map, with every start time. Spots beyond MAX_MILES are left out.
    """
    spots: dict[tuple[float, float], list[str]] = {}
    for ft in features:
        if ft.get("geometry") and ft["attributes"].get("Sample_Start_Date_Time"):
            key = (round(ft["geometry"]["y"], 5), round(ft["geometry"]["x"], 5))
            spots.setdefault(key, []).append(iso(ft["attributes"]["Sample_Start_Date_Time"]))
    return sorted(
        (
            {
                "lat": lat,
                "lon": lon,
                "kind": kind,
                "instruments": [kind],
                "readings": {kind: None},
                "start": min(starts),
                "starts": sorted(starts),
            }
            for (lat, lon), starts in spots.items()
            if miles_from_plant(lat, lon) <= MAX_MILES
        ),
        key=lambda s: (s["start"], s["lat"], s["lon"]),
    )


def summarize(
    sites: list[dict[str, Any]],
    recs: list[dict[str, Any]],
    soil: list[dict[str, Any]],
    retrieved: dt.datetime,
    water: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return the map's ``--reference-sites`` data from the three layers' features."""
    by_station: dict[str, list[dict[str, Any]]] = {}
    units = set()
    for r in recs:
        by_station.setdefault(station(r["Air_Station_ID"]), []).append(r)
        units.add(r["Mon_Units"])
    if len(units) > 1:
        raise ValueError(f"the lead layer mixes units: {sorted(units)}")
    unit = (units.pop() if units else "µg/m3").replace("m3", "m³")
    out_sites = []
    ids = [station(ft["attributes"]["Station_ID"]) for ft in sites]
    if len(ids) != len(set(ids)):
        dup = sorted({i for i in ids if ids.count(i) > 1})
        msg = f"the site list repeats station IDs: {dup}"
        raise ValueError(msg)
    for ft in sites:
        a, g = ft["attributes"], ft["geometry"]
        sid = station(a["Station_ID"])
        keys = instrument_keys(a["Instrument_Type"] or "")
        site: dict[str, Any] = {"id": sid, "lat": round(g["y"], 5), "lon": round(g["x"], 5)}
        if sid in by_station:
            site |= {"kind": "lead", "instruments": ["xact", *keys]}
        else:
            site |= {
                "kind": "realtime" if {"dusttrak", "arearae"} & set(keys) else "filter",
                "instruments": keys,
            }
        # one entry per instrument there: its results, or null until EPA posts some
        site["readings"] = dict.fromkeys(site["instruments"])
        if sid in by_station:
            recs_here = by_station.pop(sid)
            site["readings"]["xact"] = summarize_readings(recs_here, unit) | {
                "url": viewer_link(recs_here[0]["Air_Station_ID"])
            }
        out_sites.append(site)
    if by_station:
        raise ValueError(f"readings for stations not in the site list: {sorted(by_station)}")
    out_sites.sort(key=lambda s: s["id"])
    soil_out = sample_spots(soil, "soil")
    water_out = sample_spots(water or [], "water")
    when = retrieved.astimezone(dt.timezone(dt.timedelta(hours=-6)))
    when_text = f"{when:%b. %-d, %Y, %-I:%M} {'a.m.' if when.hour < 12 else 'p.m.'} CST"
    return {
        "name": "EPA sampling sites",
        "note": NOTE.format(when=when_text),
        "links": [
            {"text": "EPA's response data viewer", "url": VIEWER},
            {"text": "the monitor-placement analysis", "url": BRIEF_URL},
        ],
        "retrieved": retrieved.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ"),
        "event": EVENT.strftime("%Y-%m-%dT%H:%MZ"),
        "kinds": KINDS,
        "instruments": INSTRUMENTS,
        "sites": out_sites + soil_out + water_out,
    }


def download() -> dict[str, Any]:
    """Download the three layers now and return the summary."""
    sys.path.insert(0, str(BRIEF))
    import epa_fetch  # noqa: PLC0415 - the brief's module, found through the path above

    check_viewer()
    now = dt.datetime.now(UTC)
    sites = epa_fetch.query(epa_fetch.SITES, orderByFields="Station_ID")
    recs = [
        ft["attributes"]
        for ft in epa_fetch.query(epa_fetch.XACT, orderByFields="objectid", returnGeometry="false")
    ]
    soil = epa_fetch.query(
        f"{epa_fetch.SERVICES}/IAAAP_Soil_Sampling_Location/FeatureServer/0/query",
        orderByFields="OBJECTID_1",
    )
    water = epa_fetch.query(
        f"{epa_fetch.SERVICES}/IAAAP_Water_Sampling_Location/FeatureServer/1/query",
        orderByFields="OBJECTID_1",
    )
    far = [
        ft
        for ft in soil + water
        if ft.get("geometry")
        and miles_from_plant(ft["geometry"]["y"], ft["geometry"]["x"]) > MAX_MILES
    ]
    if far:
        sys.stdout.write(
            f"left out {len(far)} sample records more than {MAX_MILES:.0f} miles away\n"
        )
    return summarize(sites, recs, soil, now, water)


def dumps(data: dict[str, Any]) -> str:
    """Return the file's text: sorted keys, one site per line, so a refresh diffs well."""
    head = {k: v for k, v in data.items() if k != "sites"}
    body = json.dumps(head, ensure_ascii=False, indent=1, sort_keys=True)
    rows = ",\n".join(
        "  " + json.dumps(s, ensure_ascii=False, sort_keys=True) for s in data["sites"]
    )
    return body[:-2] + ',\n "sites": [\n' + rows + "\n ]\n}\n"


def main(argv: list[str] | None = None) -> None:
    """Download and write (or, with --check, compare) the file."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="print what changed; write nothing")
    ap.add_argument("-o", "--out", type=Path, default=OUT, help=f"default: {OUT.relative_to(ROOT)}")
    a = ap.parse_args(argv)
    data = download()
    lead = [s for s in data["sites"] if s["kind"] == "lead"]
    n = sum(s["readings"]["xact"]["posted"] for s in lead)
    sys.stdout.write(
        f"{data['retrieved']}: {len(data['sites'])} air sites and soil and water spots, "
        f"{len(lead)} lead monitors, {n} readings since the blast\n"
    )
    for s in lead:
        r = s["readings"]["xact"]
        sys.stdout.write(
            f"  {s['id']}: highest {r['max']['v']} at {r['max']['t']}, last {r['last']['t']}\n"
        )
    if a.check:
        return
    a.out.write_text(dumps(data), encoding="utf-8")
    sys.stdout.write(f"wrote {a.out}\n")


if __name__ == "__main__":
    main()
