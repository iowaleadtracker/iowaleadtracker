"""Rewrite the generated tables in the comparison's README from the data files.

Usage (from the repository root)::

    python scenarios/iowa-aap-lead-azide/postmortem/scripts/tables.py

Each generated table sits between ``<!-- table:NAME -->`` and ``<!-- /table:NAME -->``
in ``README.md``. The numbers come from ``data/compare.json``, ``data/army_map.json`` and
``data/forecast_vs_analysis.json`` (written by ``reproduce.sh``), so the tables can't
drift from the data. Captions and prose are written by hand.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parents[1]
ARMY_PRINTED = {"100": 29, "5": 186}  # sq mi, printed on the Army's final map
TEN = 10
MINUS = "\u2212"
DASH = "\u2013"
HUNDRED = 100


def num(x: float) -> str:
    """Format a value the way the text does: 2 significant figures or whole numbers."""
    if x == 0:
        return "0"
    if abs(x) >= HUNDRED:
        return f"{x:,.0f}"
    if abs(x) >= TEN:
        return f"{x:.0f}"
    if abs(x) >= 1:
        return f"{x:.1f}"
    if abs(x) >= 0.1:
        return f"{x:.2f}"
    return f"{x:.4f}".rstrip("0") if abs(x) >= 0.0001 else "0"


def zone(z: dict[str, float]) -> str:
    """Area / farthest distance / bearing of a zone."""
    return f"{num(z['area_mi2'])} sq mi / {num(z['reach_mi'])} mi / {z['far_bearing']:.0f}°"


def table(head: list[str], rows: list[list[str]]) -> str:
    """Return a Markdown table."""
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def wind(fva: dict[str, Any]) -> str:
    """Table 1: forecast against analysis at the plant, by level and hour."""
    hours = sorted(fva, key=int)
    names = {"15": "9 a.m.", "16": "10 a.m.", "17": "11 a.m.", "18": "Noon"}
    levels = {
        "10 m": "10 m",
        "1000 hPa": "about 40 m (1000 hPa)",
        "975 hPa": "about 240 m (975 hPa)",
        "950 hPa": "about 450 m (950 hPa)",
        "925 hPa": "about 660 m (925 hPa)",
        "900 hPa": "about 870 m (900 hPa)",
    }
    rows = []
    for key, label in levels.items():
        row = [label]
        for h in hours:
            r = next(x for x in fva[h] if x["level"] == key)
            f, a = r["forecast"], r["analysis"]
            err = f"{r['dir_error']:+.0f}°".replace("-", MINUS)
            row.append(f"{f['ms']:.1f}, {f['from']:.0f}° / {a['ms']:.1f}, {a['from']:.0f}° ({err})")
        rows.append(row)
    return table(["Level", *[names[h] for h in hours]], rows)


def models(d: dict[str, Any]) -> str:
    """Table 4: the 26% case after the reference runs' last hour."""
    cols = {
        "Tracker, forecast": "tracker forecast 26%",
        "Tracker, analyzed weather": "tracker analysis 26%",
        "HYSPLIT, ARL archive": "hysplit analysis 26%",
        "HYSPLIT, ARL archive, Emerson speeds": "hysplit analysis emerson 26%",
        "HYSPLIT, pressure-level analyses": "hysplit pressure levels 26%",
    }
    last = str(max(int(h) for h in d["runs"]["hysplit analysis 26%"]["hours"]))
    runs = {k: d["runs"][v]["hours"] for k, v in cols.items()}
    rows = [
        [f"Ground ≥ {u} µg/ft²", *[zone(r[last]["dep"][u]) for r in runs.values()]]
        for u in ("100", "40", "5")
    ]
    rows.append(
        ["Lead on the ground", *[f"{num(r[last]['deposited_lb'])} lb" for r in runs.values()]]
    )
    arcs = list(runs["Tracker, forecast"]["1"]["air_arc_max_ugm3"])
    rows += [
        [
            f"Highest hourly air, hour 1: {arc.replace('-', DASH)}",
            *[num(r["1"]["air_arc_max_ugm3"][arc]) for r in runs.values()],
        ]
        for arc in arcs
    ]
    rows.append(
        [
            "Hourly air ≥ 32 µg/m³ (PAC-1), farthest",
            *[f"{num(r['1']['pac1']['reach_mi'])} mi" for r in runs.values()],
        ]
    )
    for h in ("1", "2"):
        rows.append(
            [
                f"Center of hourly mean air, hour {h}",
                *[
                    f"{num(r[h]['mean']['center_mi'])} mi at {r[h]['mean']['center_bearing']:.0f}°"
                    for r in runs.values()
                ],
            ]
        )
    return table(["", *cols], rows)


def overlap(d: dict[str, Any]) -> str:
    """Table 5: overlap of the ground zones."""
    names = {
        "tracker forecast vs tracker analysis": "Tracker forecast vs tracker on analyzed weather",
        "tracker analysis vs hysplit analysis": (
            "Tracker on analyzed weather vs HYSPLIT (ARL archive)"
        ),
        "tracker forecast vs hysplit analysis": "Tracker forecast vs HYSPLIT (ARL archive)",
    }
    rows = []
    for key, label in names.items():
        for case in ("26%", "100%"):
            k = next(x for x in d["overlap"] if x.startswith(f"{key}, {case},"))
            o = d["overlap"][k]
            rows.append(
                [
                    label if case == "26%" else "",
                    case,
                    *[f"{o[u]['iou']:.2f}" for u in ("100", "40", "5")],
                ]
            )
    return table(["Pair", "Case", "≥ 100", "≥ 40", "≥ 5 µg/ft²"], rows)


def monitors(d: dict[str, Any]) -> str:
    """Table 6: EPA's readings and the lowest case's hourly means at each monitor."""
    cols = {
        "Tracker, forecast": "tracker forecast 7%",
        "Tracker, analyzed": "tracker analysis 7%",
        "HYSPLIT, ARL archive": "hysplit analysis 7%",
    }
    rows = []
    for name, s in sorted(d["epa_monitors"].items()):
        row = [
            name,
            f"{s['miles']:.1f} mi at {s['bearing']:.0f}°",
            str(s["n_after"]),
            str(s["nonzero_after"]),
        ]
        row += [
            f"{s['max_after_ugm3']:.4f}",
            f"{s['max_before_ugm3']:.4f}" if s["max_before_ugm3"] else "0",
        ]
        for key in cols.values():
            m = d["at_monitors"][key][name]
            row.append(" / ".join(num(m[h]["at"]) for h in ("1", "2")))
        rows.append(row)
    head = [
        "Monitor",
        "From the plant",
        "Readings after 9 a.m.",
        "Not zero",
        "Highest (µg/m³)",
        "Highest before 9 a.m.",
    ]
    return table([*head, *[f"{c} (h1 / h2)" for c in cols]], rows)


def army(d: dict[str, Any], a: dict[str, Any]) -> str:
    """Table 7: the Army's final map against the tracker's 26% case."""
    f = a["final"]
    tip, box = f["anchors"]["tip"], f["anchors"]["box"]
    tr = {k: d["runs"][f"tracker {k} 26%"]["hours"] for k in ("forecast", "analysis")}
    rows = []
    for u in ("100", "5"):
        g = f"ground_{u}"
        rows.append(
            [
                f"Ground ≥ {u} µg/ft²: area",
                f"{ARMY_PRINTED[u]} sq mi (printed)",
                *[f"{num(t['8']['dep'][u]['area_mi2'])} sq mi" for t in tr.values()],
            ]
        )
        t_, b_ = tip[g], box[g]
        army_cell = (
            f"{t_['far_mi']:.0f} mi ({b_['far_mi']:.0f}), "
            f"{t_['far_bearing']:.0f}° ({b_['far_bearing']:.0f}°)"
        )
        rows.append(
            [
                "farthest, bearing",
                army_cell,
                *[
                    f"{num(z_['reach_mi'])} mi, {z_['far_bearing']:.0f}°"
                    for z_ in (t["8"]["dep"][u] for t in tr.values())
                ],
            ]
        )
    axes = f"{f['ground_axis_bearing']:.0f}° on the ground, "
    axes += f"{f['air_path']['axis_bearing']:.0f}° in air"
    rows.append(["Plume axis", axes, "", ""])
    ov = []
    for k in tr:
        t_iou = tip["overlap_ground_5"][f"tracker {k}"]["iou"]
        b_iou = box["overlap_ground_5"][f"tracker {k}"]["iou"]
        ov.append(f"{t_iou:.2f} ({b_iou:.2f})")
    rows.append(["Overlap of the 5 µg/ft² zones with the Army's", "", *ov])
    for h, cut in f["air_cuts"].items():
        if h not in tr["forecast"]:
            continue
        cells = []
        for t in tr.values():
            s = t[h]["snapshot"]
            ext = f"{s['air018']['near_mi']:.0f}{DASH}{s['air018']['reach_mi']:.0f} mi"
            cells.append(f"{ext}, center {s['center_mi']:.0f} mi at {s['center_bearing']:.0f}°")
        rows.append([f"Cloud at {h} h", f"{cut['miles']:.0f} mi", *cells])
    return table(["", "Army, final map", "Tracker, forecast", "Tracker, analyzed weather"], rows)


def sensitivity(d: dict[str, Any], a: dict[str, Any]) -> str:
    """Table 8: the tracker under other assumptions, with the Army's map."""
    labels = {
        "baseline (fine sizes, Zhang)": "As published: fine sizes (0.3–10 µm), Zhang deposition",  # noqa: RUF001
        "sizes 1-30 µm (mixed)": "Sizes 1–30 µm (`mixed`)",  # noqa: RUF001
        "sizes 10-100 µm (soil-bound)": "Sizes 10–100 µm (`soil-bound`)",  # noqa: RUF001
        "half fine, half 30 and 100 µm": "Half fine, half 30 and 100 µm",
        "fine sizes, deposition speed +1 cm/s": "Fine sizes, deposition speed +1 cm/s",
        "fine sizes, Emerson deposition": "Fine sizes, Emerson deposition",
        "fine sizes, cloud top 151 m": "Fine sizes, cloud top 151 m instead of 251 m",
    }
    rows = []
    for key, label in labels.items():
        v = d["sensitivity_26pct_8h"][key]
        z = v["dep"]
        rows.append(
            [
                label,
                *[
                    f"{num(z[u]['area_mi2'])} sq mi, {num(z[u]['reach_mi'])} mi"
                    for u in ("100", "5")
                ],
                f"{num(v['deposited_within_15mi_lb'])} lb",
            ]
        )
    tip = a["final"]["anchors"]["tip"]
    cells = [
        f"**{ARMY_PRINTED[u]} sq mi, {tip[f'ground_{u}']['far_mi']:.0f} mi**" for u in ("100", "5")
    ]
    rows.append(["**Army, final map**", *cells, "not given"])
    return table(["Run", "≥ 100 µg/ft²", "≥ 5 µg/ft²", "Lead on the ground within 15 mi"], rows)


def main() -> None:
    """Rewrite every marked table in README.md."""
    d = json.loads((HERE / "data/compare.json").read_text())
    a = json.loads((HERE / "data/army_map.json").read_text())
    fva = json.loads((HERE / "data/forecast_vs_analysis.json").read_text())
    blocks = {
        "wind": wind(fva),
        "models": models(d),
        "overlap": overlap(d),
        "monitors": monitors(d),
        "army": army(d, a),
        "sensitivity": sensitivity(d, a),
    }
    path = HERE / "README.md"
    text = path.read_text()
    for name, body in blocks.items():
        start, end = f"<!-- table:{name} -->\n", f"\n<!-- /table:{name} -->"
        if start not in text or end not in text:
            msg = f"marker for table '{name}' not found in README.md"
            raise SystemExit(msg)
        i = text.index(start) + len(start)
        text = text[:i] + body + text[text.index(end, i) :]
    path.write_text(text)


if __name__ == "__main__":
    main()
