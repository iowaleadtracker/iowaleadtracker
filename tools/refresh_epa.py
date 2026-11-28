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
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SCENARIO = ROOT / "scenarios" / "iowa-aap-lead-azide"
BRIEF = SCENARIO / "postmortem" / "monitor-placement-brief"
OUT = SCENARIO / "epa_sites.json"
UTC = dt.timezone.utc
#: The detonation, 9 a.m. CST Nov. 25, 2026 (as the brief's RELEASE_UTC): readings at or
#: after it are "since the blast", earlier ones are the baseline.
EVENT = dt.datetime(2026, 11, 25, 15, 0, tzinfo=UTC)
VIEWER = "https://experience.arcgis.com/experience/1ddcf8b9d8314971b00dac8893ae9cd6"
BRIEF_URL = "https://iowaleadtracker.com/monitor-placement/"

#: What each instrument is, for the map's detail view. Keep these to what the sources say:
#: Xact and the air cassette from the monitor-placement brief (EPA 2026a, 2026b there);
#: DustTrak from TSI's DustTrak II 8530 page, AreaRAE from Honeywell's AreaRAE Pro RAEMet
#: sensor page, the Summa canister from EPA Compendium Method TO-15 (EPA/625/R-96/010b,
#: 1999). All three are in works_cited.py (checked 28 November 2026).
INSTRUMENTS: dict[str, dict[str, str]] = {
    "xact": {
        "name": "Xact continuous lead monitor",
        "text": "Collects particles from the air on a filter tape and measures their metals "
        "by X-ray fluorescence as it runs, so its readings post without a lab. EPA "
        "hasn't published the model, inlet size or detection limit.",
    },
    "cassette": {
        "name": "Air cassette",
        "text": "A filter that collects particles from the air. A lab measures the lead on "
        "it; no results had been posted.",
    },
    "dusttrak": {
        "name": "DustTrak",
        "text": "A light-scattering laser photometer that gives real-time readings of the "
        "mass of particles in the air (TSI). It measures all particles, not lead. No "
        "readings had been posted.",
    },
    "arearae": {
        "name": "AreaRAE",
        "text": "A wireless monitor for up to seven hazards, among them volatile organic "
        "compounds, combustible and toxic gases, oxygen and gamma radiation (Honeywell). "
        "It doesn't measure lead in dust.",
    },
    "summa": {
        "name": "Summa canister",
        "text": "A specially prepared stainless steel canister that takes in a sample of "
        "air for a lab to test for volatile organic compounds (EPA Method TO-15), not lead.",
    },
    "soil": {
        "name": "Soil sample",
        "text": "EPA lists where and when it started sampling soil. No results had been posted.",
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
#: for these; the diamond and square follow the monitor-placement brief's map.
KINDS: dict[str, dict[str, str]] = {
    "lead": {"label": "Continuous lead monitor (Xact)", "shape": "diamond"},
    "realtime": {"label": "Air filter, with dust and gas monitors", "shape": "square-dot"},
    "filter": {"label": "Air filter and gas canister", "shape": "square"},
    "soil": {"label": "Soil sampling location", "shape": "triangle"},
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


def summarize_readings(recs: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize one monitor's readings: since the blast, before it, and the last one."""
    rows = sorted((r["Mon_Date_Time"], float(r["Mon_Results"])) for r in recs)
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
        "posted": len(after),
        "zero": sum(v == 0 for _, v in after),
        "max": peak(after),
        "maxBefore": peak(before),
        "first": iso(rows[0][0]),
        "last": {"v": v_last, "t": iso(t_last)},
    }


def summarize(
    sites: list[dict[str, Any]],
    recs: list[dict[str, Any]],
    soil: list[dict[str, Any]],
    retrieved: dt.datetime,
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
    for ft in sites:
        a, g = ft["attributes"], ft["geometry"]
        sid = station(a["Station_ID"])
        keys = instrument_keys(a["Instrument_Type"] or "")
        site: dict[str, Any] = {"id": sid, "lat": round(g["y"], 5), "lon": round(g["x"], 5)}
        if sid in by_station:
            site |= {"kind": "lead", "instruments": ["xact", *keys]}
            site["readings"] = summarize_readings(by_station.pop(sid))
        else:
            site |= {
                "kind": "realtime" if {"dusttrak", "arearae"} & set(keys) else "filter",
                "instruments": keys,
            }
        out_sites.append(site)
    if by_station:
        raise ValueError(f"readings for stations not in the site list: {sorted(by_station)}")
    out_sites.sort(key=lambda s: s["id"])
    soil_out = sorted(
        (
            {
                "lat": round(ft["geometry"]["y"], 5),
                "lon": round(ft["geometry"]["x"], 5),
                "kind": "soil",
                "instruments": ["soil"],
                "start": iso(ft["attributes"]["Sample_Start_Date_Time"]),
            }
            for ft in soil
            if ft.get("geometry") and ft["attributes"].get("Sample_Start_Date_Time")
        ),
        key=lambda s: (s["start"], s["lat"], s["lon"]),
    )
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
        "unit": unit,
        "kinds": KINDS,
        "instruments": INSTRUMENTS,
        "sites": out_sites + soil_out,
    }


def download() -> dict[str, Any]:
    """Download the three layers now and return the summary."""
    sys.path.insert(0, str(BRIEF))
    import epa_fetch  # noqa: PLC0415 - the brief's module, found through the path above

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
    return summarize(sites, recs, soil, now)


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
    n = sum(s["readings"]["posted"] for s in lead)
    sys.stdout.write(
        f"{data['retrieved']}: {len(data['sites'])} sites and soil points, "
        f"{len(lead)} lead monitors, {n} readings since the blast\n"
    )
    for s in lead:
        r = s["readings"]
        sys.stdout.write(
            f"  {s['id']}: highest {r['max']['v']} at {r['max']['t']}, last {r['last']['t']}\n"
        )
    if a.check:
        return
    a.out.write_text(dumps(data), encoding="utf-8")
    sys.stdout.write(f"wrote {a.out}\n")


if __name__ == "__main__":
    main()
