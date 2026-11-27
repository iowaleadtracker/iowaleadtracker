"""The site's safety wording and settings can't silently disappear.

The warnings ("unofficial", "not from the Army", "don't use it to decide if you're
safe", the caveat after every town list) are the project's main protection against
being read as an official safety map. These tests build a small set of maps offline
and check that every place the text is generated still carries them.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import math
import re
from pathlib import Path
from typing import Any

import forecast_summary as fs
import make_map_picker as site
import pytest
import staged
import works_cited

from dispersal import met
from dispersal.output import load_template, write_html
from tools import compare_site

from .conftest import run_puff

NOT_SAFE = "Don't use"
UNOFFICIAL = "unofficial estimate, not from the Army or any government agency"


@pytest.fixture(scope="module")
def facts_ctx(tmp_path_factory: pytest.TempPathFactory) -> tuple[dict[str, Any], dict[str, Any]]:
    """Facts and build context for four noon maps under a steady north wind."""
    folder = tmp_path_factory.mktemp("maps")
    maps: dict[tuple[str, str], str | Path] = {}
    pct = {}
    args = list(site.MODEL_ARGS)
    for flag in ("--weather-model", "--met-cache"):  # offline: a steady wind instead
        i = args.index(flag)
        del args[i : i + 2]
    for case, release_case, _ in site.CASES:
        a, out = run_puff(
            [
                *("--lat", str(site.LAT)),
                *("--lon", str(site.LON)),
                *("--time", f"{site.DATE}T12:00-06:00"),
                *("--release-case", release_case),
                *args,
                *("--wind", "3@0", "--wind-grid", "1", "--grid", "120"),
            ]
        )
        path = folder / site.map_name(case, "12:00")
        write_html(out, path)
        maps[(case, "12:00")] = path
        pct[case] = f"{a.airborne_fraction * 100:.0f}%"
    facts = fs.facts(maps, site.CASES, ["12:00"], "12:00")
    ctx: dict[str, Any] = {
        "pct": pct,
        "got_txt": "November 20, 2026, at 10:00 a.m. CST",
        "n_models": "one",
        "built_txt": "November 20, 2026, at 10:13 a.m. CST",
        "site_name": site.SITE_NAME,
        "site_url": site.SITE_URL,
        "description": site.DESCRIPTION,
        "lat": site.LAT,
        "lon": site.LON,
    }
    return facts, ctx


@pytest.fixture(scope="module")
def rendered(facts_ctx: tuple[dict[str, Any], dict[str, Any]]) -> tuple[str, list, str]:
    """Summary HTML, FAQ and llms.txt for the planned day only."""
    return fs.render(*facts_ctx)


@pytest.fixture(scope="module")
def rendered_two_days(facts_ctx: tuple[dict[str, Any], dict[str, Any]]) -> tuple[str, list, str]:
    """Render it again with the same maps standing in for Thursday as a second day.

    (The site's Thursday is menu-only; this checks the text for any later day named.)
    """
    facts, ctx = facts_ctx
    thursday = {**facts, "day": "Thursday, Nov. 26", "n_models": "two"}
    return fs.render(facts, ctx, [thursday])


@pytest.mark.slow
def test_summary_carries_the_warnings(rendered: tuple[str, list, str]) -> None:
    summary, _, _ = rendered
    assert fs.CAVEAT in summary
    assert fs.TOWN_CAVEAT in summary


@pytest.mark.slow
def test_every_faq_answer_about_places_has_the_town_caveat(rendered: tuple[str, list, str]) -> None:
    _, faq, _ = rendered
    answers = dict(faq)
    assert any(NOT_SAFE in a for a in answers.values())
    for question, answer in faq:
        if "yellow area" in answer or "case reaches" in answer:
            assert fs.TOWN_CAVEAT in answer, question


@pytest.mark.slow
def test_llms_txt_leads_with_the_warning(rendered: tuple[str, list, str]) -> None:
    _, _, llms = rendered
    head = llms[: llms.index("## About")]
    assert NOT_SAFE in head
    assert "not from the Army" in head
    assert fs.TOWN_CAVEAT in llms


@pytest.mark.slow
def test_analysis_after_the_blast_is_reported_with_its_caveat(
    rendered: tuple[str, list, str],
) -> None:
    """The summary, the questions and llms.txt report the monitor-placement analysis.

    Each says what it found in the same words, that it is preliminary and unofficial, and
    where to read it. None of them says anything about a place being safe.
    """
    summary, faq, llms = rendered
    assert "not measurements" in fs.ANALYSIS
    assert "preliminary, unofficial analysis" in fs.ANALYSIS
    assert "safe" not in fs.ANALYSIS.lower()
    shown = html.escape(fs.ANALYSIS, quote=False)
    assert f"<h3>{fs.ANALYSIS_QUESTION}</h3>\n  <p>{shown}" in summary
    assert f'<a href="{works_cited.ANALYSIS_PATH}">Read the preliminary analysis</a>' in summary
    assert summary.index(fs.ANALYSIS_QUESTION) < summary.index("How sure is this?")
    answer = dict(faq)[fs.ANALYSIS_QUESTION]
    assert answer.startswith(fs.ANALYSIS)
    assert works_cited.ANALYSIS_URL in answer
    assert answer.endswith(fs.CAVEAT)
    assert f"(preliminary analysis): {fs.ANALYSIS}" in llms
    assert f"- [Preliminary analysis]({works_cited.ANALYSIS_URL})" in llms


@pytest.mark.slow
def test_summary_questions_and_llms_describe_the_default_view(
    facts_ctx: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    """With archived maps built, the text leads with what the map opens on.

    The same maps stand in for the archived ones here. The archived section comes before
    the forecast sections, which are labeled as the forecast from before the blast, and
    every list of towns keeps its caveat.
    """
    facts, ctx = facts_ctx
    summary, faq, llms = fs.render(facts, {**ctx, "archived": facts})
    view = fs.default_view(ctx["pct"]["low"])
    assert f"<h3>{fs.DEFAULT_VIEW_HEAD}</h3>\n  <p>{view}</p>" in summary
    order = [
        fs.DEFAULT_VIEW_HEAD,
        fs.ARCHIVED_HEAD,
        fs.FORECAST_HEAD,
        "Where the cloud goes",
        "How sure is this?",
    ]
    spots = [summary.index(f"<h3>{h}") for h in order]
    assert spots == sorted(spots)
    assert summary.index("When was the detonation?") < spots[0]
    assert "In the archived weather, winds near the ground at blast time were from the" in summary
    assert summary.count(fs.TOWN_CAVEAT) == 2  # the archived towns and the forecast towns
    assert "(the map\u2019s default)" not in summary  # the permit case no longer is
    answers = dict(faq)
    opens = answers[fs.DEFAULT_VIEW_QUESTION]
    assert opens.startswith(fs.default_view(ctx["pct"]["low"]))
    assert fs.TOWN_CAVEAT in opens
    assert opens.endswith(fs.CAVEAT)
    assert answers["Where could the lead go?"].startswith(fs.FORECAST_PREFIX)
    assert answers["How far could lead on the ground reach?"].startswith(fs.FORECAST_PREFIX)
    assert "- Default view and archived weather: " + fs.default_view(ctx["pct"]["low"]) in llms
    # llms.txt labels its forecast lines too: an answer engine quotes single lines
    for line in llms.splitlines():
        if line.startswith("- ") and ("yellow area" in line or "were forecast" in line):
            assert line.startswith("- " + fs.FORECAST_PREFIX) or "archived weather" in line, line
    assert "blast-time menu" not in summary
    assert "each case and blast time" not in summary
    # without archived maps the text is as before
    plain_summary, plain_faq, plain_llms = fs.render(facts, ctx)
    assert fs.DEFAULT_VIEW_HEAD not in plain_summary
    assert fs.DEFAULT_VIEW_QUESTION not in dict(plain_faq)
    assert "Default view and archived weather" not in plain_llms
    assert not dict(plain_faq)["Where could the lead go?"].startswith(fs.FORECAST_PREFIX)


def test_header_and_about_box_name_the_weather() -> None:
    page = site.PAGE_TEMPLATE.read_text(encoding="utf-8")
    assert "Follow official instructions. $weather_line</span>" in page
    assert "$about_weather If the actual" in " ".join(page.split())
    line = fs.weather_line("X", archived=True)
    assert (
        line
        == "Weather: archived (NOAA HRRR, saved Nov. 25, 6:51 p.m. CST), or the forecast from X."
    )
    assert fs.weather_line("X", archived=False) == "Weather forecast from X."
    about = fs.about_weather("four", "X", archived=True)
    assert about.startswith(
        "The map opens on the low case, the smallest of the four; that is not a finding that "
        "little lead got out. It opens on archived weather: NOAA\u2019s HRRR weather model"
    )
    assert "from four weather forecasts, current as of X" in about
    assert "not a measurement" in about
    assert fs.about_weather("four", "X", archived=False) == (
        "The winds come from four weather forecasts, current as of X."
    )
    nov26 = [what for when, what in works_cited.CHANGES if when == "Nov. 26"]
    assert works_cited.CHANGES[0][0] == "Nov. 27"  # the newest entry (the Army's final forecast)
    assert any("opens on a 9 a.m. blast, the low case, and archived weather" in w for w in nov26)
    assert any(
        "Opening on the low case is not a finding that little lead got out." in w for w in nov26
    )


def test_analysis_in_the_header_about_box_and_methodology() -> None:
    page = site.PAGE_TEMPLATE.read_text(encoding="utf-8")
    about = " ".join(dialog(page, "note").split())
    assert "<p><b>$analysis_head</b> $analysis</p>" in about
    assert about.index("What the map shows.") < about.index("$analysis_head")
    assert about.index("$analysis_head") < about.index("decide if you&rsquo;re safe")
    assert works_cited.ANALYSIS_PATH in fs.EARLY_AIR_HTML
    assert "unofficial model estimates, not measurements" in fs.EARLY_AIR_HTML
    ctx: dict[str, Any] = {
        "pct": {"low": "7%", "mid": "26%", "high": "55%", "permit": "100%"},
        "n_models": "two",
        "got_txt": "now",
        "shown_model": "GFS",
        "models": [],
    }
    body = works_cited.render(ctx, "https://example.org/", "now")
    method = f"<p><b>{works_cited.ANALYSIS_HEAD}</b> {works_cited.ANALYSIS_METHOD}</p>"
    assert body.index(works_cited.METHOD_HEAD) < body.index(method)
    assert body.index(method) < body.index(f"<h3>{works_cited.CHANGES_HEAD}</h3>")
    assert "no official source confirms that location" in works_cited.ANALYSIS_METHOD
    assert works_cited.ANALYSIS_FOLDER_URL in works_cited.ANALYSIS_METHOD
    what = next(w for d, w in works_cited.CHANGES if d == "Nov. 26" and "analysis" in w)
    assert works_cited.ANALYSIS_PATH in what
    assert "The maps did not change." in what
    # the two papers the method names are in the reference list
    assert any(r.startswith("Dowell, D. C.") for r in works_cited.REFERENCES if isinstance(r, str))
    assert any(r.startswith("Stein, A. F.") for r in works_cited.REFERENCES if isinstance(r, str))


@pytest.mark.slow
def test_no_private_citizen_in_warnings(rendered: tuple[str, list, str]) -> None:
    summary, faq, llms = rendered
    for text in (summary, llms, *(a for _, a in faq)):
        assert "private citizen" not in text


def test_page_templates_carry_the_warning() -> None:
    page = " ".join(site.PAGE_TEMPLATE.read_text(encoding="utf-8").split())
    assert f"This is an {UNOFFICIAL}" in page
    assert "Don't use it to decide if you're safe" in page
    maps = " ".join(load_template().split())
    assert "Unofficial estimate, not from the Army or any government agency" in maps
    assert "Unofficial estimate" in maps  # the legend line on every map


def test_town_caveat_wording() -> None:
    assert "may still get lead" in fs.TOWN_CAVEAT
    assert "none you could measure" in fs.TOWN_CAVEAT


def test_security_headers() -> None:
    assert "frame-ancestors 'self'" in site.CSP
    assert "default-src 'none'" in site.CSP
    assert "geolocation=()" in site.PERMISSIONS
    assert "Strict-Transport-Security" in site.HEADERS


def test_blast_label_names_the_date() -> None:
    assert site.blast_label("12:00") == "Wednesday, Nov. 25, 2026, 12:00 p.m. CST"
    assert site.blast_label("11:15") == "Wednesday, Nov. 25, 2026, 11:15 a.m. CST"


def test_pulled_label_for_the_legend() -> None:
    pulled = dt.datetime(2026, 11, 21, 12, 49, tzinfo=site.TZ)
    assert site.pulled_label(pulled) == "Nov. 21, 12:49 p.m. CST"
    morning = dt.datetime(2026, 11, 21, 8, 8, tzinfo=site.TZ)
    assert site.pulled_label(morning) == "Nov. 21, 8:08 a.m. CST"


def test_page_opens_on_the_low_case_and_says_it_is_not_a_finding() -> None:
    """Since Nov. 26 the page opens on the low case (maintainer's choice, after the blast).

    Before the blast it opened on the EPA permit case, to avoid a false sense of security.
    The larger cases stay in the menu, and wherever the page says what it opens on, it
    also says that this is not a finding that little lead got out.
    """
    assert site.DEFAULT_CASE == "low"
    assert {c: r for c, r, _ in site.CASES}["permit"] == "permit-100"
    assert [c for c, _, _ in site.CASES] == ["low", "mid", "high", "permit"]
    view = fs.default_view("7%")
    assert "the low case (7% of the lead in the air)" in view
    assert "is not a finding that little lead got out" in view
    assert "up to the EPA permit case, which assumes all of the lead got into the air" in view
    assert "not a measurement of where the cloud went" in view
    assert "safe" not in view.lower()


def test_weather_menu_opens_on_archived_weather(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Archived weather first, the pre-blast forecast second; forecast maps keep their names."""
    assert [s for s, _ in site.SOURCES] == ["archived", "forecast"]
    assert site.ARCHIVED_CACHE.exists()  # saved in the repository: a build never downloads it
    assert site.map_name("low", "09:00") == "low-0900.html"
    assert site.map_name("low", "09:00", site.DATE, "archived") == "archived-low-0900.html"
    assert site.map_key(site.DATE, "low", "09:00") == f"{site.DATE}-low-0900"
    assert site.map_key(site.DATE, "low", "09:00", "archived") == f"archived-{site.DATE}-low-0900"
    page = site.PAGE_TEMPLATE.read_text(encoding="utf-8")
    assert '<label for="w"$source_hidden>Weather' in page
    assert '<select id="w">$source_options</select>' in page
    assert '<label for="t"$time_hidden>' in page  # one blast time: the time menu is hidden
    assert "(src.value === OPEN_SOURCE ? '' : '-' + src.value)" in page
    # with only the forecast maps built, the page opens on them and hides the menu
    monkeypatch.setattr(site, "MAPS", tmp_path)
    for c, _, _ in site.CASES:
        (tmp_path / site.map_name(c, "09:00")).write_text("x", encoding="utf-8")
    only = site.source_values(
        site.Maps([], {}, ["09:00"], "09:00", sources=site.sources_built(["09:00"]))
    )
    assert only["open_source"] == '"forecast"'
    assert only["source_hidden"] == " hidden"
    assert only["time_hidden"] == " hidden"
    for c, _, _ in site.CASES:
        (tmp_path / site.map_name(c, "09:00", site.DATE, "archived")).write_text(
            "x", encoding="utf-8"
        )
    both = site.source_values(
        site.Maps([], {}, ["09:00"], "09:00", sources=site.sources_built(["09:00"]))
    )
    assert both["open_source"] == '"archived"'
    assert both["source_hidden"] == ""
    assert both["source_options"].index("Archived weather") < both["source_options"].index(
        "Forecast"
    )
    assert '<option value="archived" selected>' in both["source_options"]


def test_archived_map_runs_offline_from_the_new_release_point(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The archived weather, saved around the plant point, serves a run from the magazines.

    A quick, coarse run with the site's own archived settings and downloads off. Without
    --weather-at the same run would need weather centered on the new point, which isn't
    saved, so it stops instead of downloading.
    """
    monkeypatch.setenv(site.CACHE_ONLY_ENV, "1")
    cmd = site.archived_runs("python")[0].cmd
    argv = cmd[2 : cmd.index("-o")]  # the options, without the interpreter and the output
    for flag, value in (("--grid", "60"), ("--dt", "300")):
        argv[argv.index(flag) + 1] = value
    _, out = run_puff(argv)
    meta = out["meta"]
    assert (meta["lat"], meta["lon"]) == (site.ARCHIVED_LAT, site.ARCHIVED_LON)
    assert meta["weather"] == site.ARCHIVED_LABEL  # not "Open-Meteo forecast"
    assert "sky" not in out["hours"][0]
    spread = meta["ensemble"]
    assert not spread["models"]  # one weather source: the template's deposition-only wording
    assert not spread["spread"]
    assert len(spread["deposition"]) == 2
    assert out["hours"][0]["ws"] > 0
    # the saved HYSPLIT run rides along, on the map's grid and scaled to this case
    grid = out["grid"]
    assert {"hy_conc", "hy_dep"} <= set(grid)
    note = meta["hysplitOverlay"]
    assert note["file"] == site.HYSPLIT_OVERLAY.name
    assert note["note"] == site.HYSPLIT_NOTE
    assert note["scaledBy"] == pytest.approx(meta["explosionOpts"]["airborneFraction"], rel=1e-4)
    assert len(note["airMax"]) == len(note["depMax"]) == len(out["hours"])  # HYSPLIT's peaks
    # the Army's final maps ride along as outlines for the box under the map
    assert meta["outlines"]["name"] == "Army\u2019s final forecast"
    assert len(meta["outlines"]["dep"]["zones"]) == 2
    # the deposition view's minimum, 5 ug/ft2 in the page's kg/m2
    assert meta["depScaleMin"] == pytest.approx(5e-9 / 0.09290304)
    # two models, one release: their highest hourly means agree within a factor of 3
    assert 1 / 3 < grid["hy_conc"]["max"] / grid["conc"]["max"] < 3
    i = argv.index("--weather-at")
    with pytest.raises(met.NotSaved):
        run_puff(argv[:i] + argv[i + 2 :])


def test_hashed_names_cover_both_weather_sets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Archived maps get their own keys and hashed files; the comparison tool reads past both."""
    monkeypatch.setattr(site, "MAPS", tmp_path / "maps")
    monkeypatch.setattr(site, "HASHED", tmp_path / "m")
    site.MAPS.mkdir()
    for source in ("forecast", "archived"):
        for c, _, _ in site.CASES:
            name = site.map_name(c, "09:00", site.DATE, source)
            (site.MAPS / name).write_text(f"<html><head></head>{name}</html>", encoding="utf-8")
    files = site.write_hashed_maps({site.DATE: ["09:00"]}, ["archived", "forecast"])
    assert sorted(files) == sorted(
        site.map_key(site.DATE, c, "09:00", s)
        for s in ("forecast", "archived")
        for c, _, _ in site.CASES
    )
    assert re.fullmatch(
        r"m/archived-low-0900-[0-9a-f]{10}", files[f"archived-{site.DATE}-low-0900"]
    )
    assert re.fullmatch(r"m/low-0900-[0-9a-f]{10}", files[f"{site.DATE}-low-0900"])
    page = 'rel="canonical"' in (site.MAPS / "archived-low-0900.html").read_text(encoding="utf-8")
    assert page  # a map opened on its own points search engines at the home page
    (tmp_path / "index.html").write_text(json.dumps(files), encoding="utf-8")
    cleaned = compare_site.normalized_index(tmp_path)
    assert not re.search(r"-[0-9a-f]{10}", cleaned)  # no hash left to differ between builds
    assert '"archived-low-0900"' in cleaned  # the tool keeps the name and drops "m/" and the hash
    assert '"low-0900"' in cleaned


def test_hysplit_view_is_offered_and_described() -> None:
    """The archived maps' HYSPLIT button: off by default, labeled, explained as an estimate."""
    assert site.HYSPLIT_OVERLAY.exists()  # saved in the repository: the build never runs HYSPLIT
    page = load_template()
    assert '<div class="seg" id="modelseg" role="group" aria-label="Model" hidden>' in page
    assert '<button data-v="hysplit" aria-pressed="false">NOAA HYSPLIT</button>' in page
    assert "hy: false" in page  # the site's own model until the reader switches
    assert 'const OWN = M.homeName || "This model";' in page  # its button: the site's name
    assert "if (FIELDS.hy_conc) {" in page  # offered only on maps that carry the saved run
    # the four fixed contour colors of HYSPLIT's own plots, lowest to highest
    assert "HY_BANDS = [[0, 255, 255], [0, 255, 0], [0, 0, 255], [255, 255, 0]]" in page
    assert 'x.disabled = S.hy && !["conc", "dep"].includes(x.dataset.v)' in page  # no other views
    assert "Not a NOAA forecast." in page  # in the legend whenever HYSPLIT shows
    for text in (fs.HYSPLIT_BOX, works_cited.HYSPLIT_METHOD):
        assert "not a measurement" in text
        assert "not a forecast from NOAA" in text
        assert "safe" not in text.lower()
    assert "\u201cNOAA HYSPLIT\u201d button under the map" in fs.HYSPLIT_BOX
    assert "Stein et al. 2015" in works_cited.HYSPLIT_METHOD
    when, what = next(c for c in works_cited.CHANGES if "NOAA HYSPLIT" in c[1])
    assert when == "Nov. 27"
    assert "HYSPLIT" in what
    assert "numbers did not change" in what
    readme = (site.HYSPLIT_OVERLAY.parent / "README.md").read_text(encoding="utf-8")
    flat = " ".join(readme.split())
    assert "don't use it to decide if you're safe; follow official instructions" in flat


def test_deposition_view_opens_at_epas_lowest_action_level() -> None:
    """Deposition has a minimum like air's, with a box that brings the lower values back."""
    args = site.MODEL_ARGS
    assert args[args.index("--dep-scale-min") + 1] == "5ug/ft2"
    assert fs.DEP_LEVELS[0] == ("yellow", 5)  # the level the page already compares against
    page = load_template()
    assert "fixDepMin: !!M.depScaleMin" in page  # on when the map carries a minimum
    assert "function syncMinBox()" in page  # the box follows the view: air or deposition
    assert 'S.field === "dep" ? (S.fixDepMin && M.depScaleMin) || 0' in page
    what = next(w for _, w in works_cited.CHANGES if "deposition view" in w)
    assert "hidden, not zero" in what
    assert "not a line between safe and unsafe" in what


def test_armys_final_maps_are_offered_for_the_blast_they_were_made_for() -> None:
    """The box: off by default, on the 9 a.m. maps only, and described as the Army's forecast."""
    assert site.army_outlines(site.DATE, "09:00") == [
        "--reference-outlines",
        str(site.ARMY_OUTLINES),
    ]
    assert site.army_outlines(site.DATE, "09:30") == []  # another blast time: not its maps
    assert site.army_outlines("2026-11-27", "09:00") == []
    for run in site.archived_runs("python"):
        assert "--reference-outlines" in run.cmd
    page = load_template()
    assert '<label class="opt" id="refwrap" hidden><input type="checkbox" id="showRef">' in page
    assert "ref: false" in page  # off until the reader ticks it
    assert "if (M.outlines) {" in page  # offered only on maps that carry outlines
    for text in (fs.ARMY_BOX, works_cited.ARMY_BOX_METHOD, works_cited.CHANGES[0][1]):
        assert "26% of the lead airborne" in text
        assert "0.6 mile" in text  # how well the pictures could be placed
        assert "safe" not in text.lower()
    readme = (site.ARMY_OUTLINES.parent / "README.md").read_text(encoding="utf-8")
    flat = " ".join(readme.split())
    assert "don't use this to decide if you're safe; follow official instructions" in flat


def test_armys_outlines_are_southwest_of_the_plant() -> None:
    """The traced file: an air path with four time marks, two ground zones, all near the plant."""
    data = json.loads(site.ARMY_OUTLINES.read_text(encoding="utf-8"))
    assert data["name"] == "Army\u2019s final forecast"
    assert "Traced and placed by this site" in data["note"]
    # how far the Army's marker hides its zones: measured, and said the same way everywhere
    miles = data["hiddenMiles"]
    starts = [
        min(math.hypot((la - 40.8096) * 69.09, (lo + 91.2692) * 69.09 * 0.757) for la, lo in ln)
        for kind in ("air", "dep")
        for z in data[kind]["zones"]
        for ln in z["lines"]
    ]
    assert miles - 1 < min(starts) < max(starts) < miles + 1
    assert f"first {miles} miles" in data["note"]
    assert f"first {miles} miles" in fs.ARMY_BOX
    assert f"first {miles} miles" in works_cited.ARMY_BOX_METHOD
    # where the Army posted the two maps, linked from the legend, the summary and the references
    assert [ln["url"] for ln in data["links"]] == [fs.ARMY_AIR_MAP_URL, fs.ARMY_GROUND_MAP_URL]
    assert fs.ARMY_AIR_MAP_URL.endswith("/image/10118629/deposition-map-2-800-am-cst")
    assert fs.ARMY_GROUND_MAP_URL.endswith("/image/10118630/deposition-map-1-800-am-cst")
    assert fs.ARMY_AIR_MAP_URL in fs.ARMY_BOX_LINKS_HTML
    assert fs.ARMY_GROUND_MAP_URL in fs.ARMY_BOX_LINKS
    refs = [r for r in works_cited.REFERENCES if isinstance(r, str)]
    assert any(r.startswith("McFate, L., 2026e:") and fs.ARMY_GROUND_MAP_URL in r for r in refs)
    assert any(r.startswith("McFate, L., 2026f:") and fs.ARMY_AIR_MAP_URL in r for r in refs)
    assert [m["label"] for m in data["air"]["marks"]] == ["T+0.5 h", "T+2 h", "T+3 h", "T+5 h"]
    assert [z["label"].split()[0] for z in data["dep"]["zones"]] == ["5", "100"]
    for kind in ("air", "dep"):
        for zone in data[kind]["zones"]:
            pts = [pt for line in zone["lines"] for pt in line]
            assert len(pts) > 20
            # the Army's forecast went southwest: nothing north or east of the plant point
            assert all(39.5 < lat < site.LAT and -93.0 < lon < site.LON for lat, lon in pts)


def test_staged_page_keeps_the_permit_case_first() -> None:
    """The Wednesday-to-Friday forecasts from before the blast open as they did then."""
    assert staged.DEFAULT_CASE == "permit"
    assert site.DEFAULT_CASE == "low"


def test_archived_runs_use_only_the_saved_weather() -> None:
    runs = site.archived_runs("python")
    assert [r.which for r in runs] == [f"archived {c} 09:00" for c, _, _ in site.CASES]
    for r in runs:
        cmd = r.cmd
        assert cmd[cmd.index("--weather-model") + 1] == site.ARCHIVED_MODEL
        assert cmd[cmd.index("--met-cache") + 1] == str(site.ARCHIVED_CACHE)
        assert cmd[cmd.index("--as-of") + 1] == site.ARCHIVED_AS_OF
        assert "--sky-grid" not in cmd  # the sky grid is a forecast
        assert "--no-sky-layer" in cmd  # and so is the map's own sky layer, by its label
        # NOAA's HYSPLIT result for the same blast, for the "NOAA HYSPLIT" button
        assert cmd[cmd.index("--hysplit-overlay") + 1] == str(site.HYSPLIT_OVERLAY)
        assert cmd[cmd.index("--hysplit-overlay-note") + 1] == site.HYSPLIT_NOTE
        assert cmd[cmd.index("--home-name") + 1] == "Iowa Lead Tracker"  # the other button
        assert cmd[cmd.index("--weather-label") + 1].startswith("archived NOAA HRRR")
        # from midway between the two magazines, on the weather saved around the plant point
        assert cmd[cmd.index("--lat") + 1] == "40.8096"
        assert cmd[cmd.index("--lon") + 1] == "-91.2692"
        assert cmd[cmd.index("--weather-at") + 1] == f"{site.LAT},{site.LON}"
        assert (
            "archived weather (NOAA HRRR, saved Nov. 25, 6:51 p.m. CST)"
            in cmd[cmd.index("--legend-note") + 1]
        )
        assert r.out.name.startswith("archived-")


def test_references_are_alphabetical() -> None:
    names = [works_cited.REFERENCES[i] for i in range(len(works_cited.REFERENCES))]
    keys = [str(n[0] if isinstance(n, tuple) else n).lower() for n in names]
    assert keys == sorted(keys)


def test_accessed_date_uses_site_time_zone() -> None:
    assert works_cited.SITE_TZ.utcoffset(
        dt.datetime(2026, 11, 23, tzinfo=dt.timezone.utc)
    ) == dt.timedelta(hours=-6)


@pytest.mark.slow
def test_source_code_is_linked(rendered: tuple[str, list, str]) -> None:
    """The site points readers to the code so they can check it."""
    _, faq, llms = rendered
    assert works_cited.SOURCE_URL in dict(faq)["Who made the Iowa Lead Tracker, and why?"]
    assert f"[Source code]({works_cited.SOURCE_URL})" in llms
    assert 'href="$source_url"' in site.PAGE_TEMPLATE.read_text(encoding="utf-8")
    assert works_cited.SOURCE_URL.startswith("https://github.com/iowaleadtracker/")


def dialog(page: str, dialog_id: str) -> str:
    """Return the template's ``<dialog id=...>`` element (note: About; cite: Methodology)."""
    start = page.index(f'<dialog id="{dialog_id}"')
    return page[start : page.index("</dialog>", start)]


def test_court_pause_note_in_about_dialog() -> None:
    """About gives the Eighth Circuit ruling in one linked sentence; Methodology the full case."""
    page = site.PAGE_TEMPLATE.read_text(encoding="utf-8")
    about, cite = dialog(page, "note"), dialog(page, "cite")
    assert "<b>Court case.</b> $court_short" in about
    assert f'href="{fs.RULING_URL}"' in fs.COURT_SHORT_HTML
    assert "$court_pause" not in about
    assert "<b>Court case.</b> $court_pause" in cite
    assert "$court_sources" in cite
    assert f'href="{fs.COURT_URL}"' in fs.COURT_SOURCES_HTML
    assert f'href="{fs.RULING_URL}"' in fs.COURT_SOURCES_HTML
    assert fs.RULING_URL.startswith("https://www.kcrg.com/")  # the AP report
    assert f'href="{fs.SAND_URL}"' in fs.COURT_SOURCES_HTML
    assert fs.SAND_URL.startswith("https://www.iowapublicradio.org/")
    assert f'href="{fs.FILING_URL}"' in fs.COURT_SOURCES_HTML
    assert fs.COURT_URL.startswith("https://www.iowapublicradio.org/")
    assert "until it rules on a request" in fs.COURT_PAUSE
    assert fs.COURT_PAUSE.endswith("These maps model Wednesday, Nov. 25.")


def test_contact_in_about_citation_and_llms(rendered: tuple[str, list, str]) -> None:
    """The inbox and Instagram are in the About box, the citation, and llms.txt.

    Each time they come with the line that neither can tell anyone whether they're safe.
    """
    email = works_cited.CONTACT_EMAIL
    insta = works_cited.INSTAGRAM_URL
    assert email == "contact@iowaleadtracker.com"
    assert insta == "https://www.instagram.com/iowaleadtracker/"
    assert "follow official instructions" in works_cited.CONTACT_LIMIT
    page = site.PAGE_TEMPLATE.read_text(encoding="utf-8")
    start = page.index('<dialog id="note"')
    assert "<b>Contact.</b> $contact_html" in page[start : page.index("</dialog>", start)]
    for text in (works_cited.CONTACT_HTML, works_cited.CONTACT_TEXT):
        assert email in text
        assert "@iowaleadtracker" in text
        assert works_cited.CONTACT_LIMIT in text
    assert f'href="mailto:{email}"' in works_cited.CONTACT_HTML
    assert f'href="{insta}" rel="noopener"' in works_cited.CONTACT_HTML
    assert insta in works_cited.CONTACT_TEXT
    ctx = {
        "pct": {"low": "7%", "mid": "26%", "high": "55%", "permit": "100%"},
        "n_models": "seven",
        "got_txt": "November 21, 2026, at 5:54 p.m. CST",
        "shown_model": "RRFS",
        "models": [],
    }
    cite = works_cited.render(ctx, works_cited.SOURCE_URL, "now")
    assert works_cited.CONTACT_HTML in cite[cite.index("Citing this map") :]
    llms = rendered[2]
    assert works_cited.CONTACT_TEXT in llms[llms.index("## About") : llms.index("## Key facts")]
    assert f"- [Instagram @iowaleadtracker]({insta}): updates" in llms
    ld = json.loads(site.json_ld([], dt.datetime(2026, 11, 21, 18, 0, tzinfo=site.TZ)))
    publisher = ld["@graph"][0]["publisher"]
    assert publisher["email"] == email
    assert publisher["sameAs"] == [insta]


def test_faq_links_are_live() -> None:
    """Web addresses in FAQ answers become links; punctuation stays outside."""
    out = site.faq_html(
        [("Q?", f"Code at {works_cited.SOURCE_URL}. Source: x (https://www.army.mil/a/1).")]
    )
    assert f'<a href="{works_cited.SOURCE_URL}" rel="noopener">{works_cited.SOURCE_URL}</a>.' in out
    assert '<a href="https://www.army.mil/a/1" rel="noopener">https://www.army.mil/a/1</a>).' in out
    assert site.linkify("<b> & no links") == "&lt;b&gt; &amp; no links"
    named = site.linkify("noon (Iowa HHS fact sheet). Then (Nov. 22 court filing).")
    assert f'(<a href="{html.escape(fs.HHS_URL)}" rel="noopener">Iowa HHS fact sheet</a>)' in named
    assert f'(<a href="{fs.RESPONSE_URL}" rel="noopener">Nov. 22 court filing</a>).' in named
    cited = site.linkify(f"(Source: {fs.ARMY_WED_CITE}, {fs.ARMY_WED_URL}.)")
    assert cited == (
        f'(Source: <a href="{html.escape(fs.ARMY_WED_URL)}" rel="noopener">{fs.ARMY_WED_CITE}</a>.)'
    )


@pytest.mark.slow
def test_key_facts_lead_the_summary_and_faq(rendered: tuple[str, list, str]) -> None:
    """The time and official advice come first; how the date was set comes after."""
    summary, faq, llms = rendered
    assert summary.index("When was the detonation?") < summary.index("Where the cloud")
    assert summary.index("Where the cloud") < summary.index("How the date was set")
    assert summary.index("How the date was set") < summary.index("Court case")
    assert fs.COURT_URL in summary
    when = dict(faq)["When was the lead azide blast at the Iowa Army Ammunition Plant?"]
    assert when.startswith("As of this update (")
    assert when.index("at 9:00 a.m. CST on Wednesday, Nov. 25") < when.index(fs.TRUMP_HOLD)
    assert "had planned it for about 9 a.m." not in when  # said once, in the first sentence
    assert fs.ADVISORY_NOV24_URL in when
    assert (
        "The Army had "
        "planned Monday, Nov. 23. On Nov. 22, the government told the court, which had put "
        "the permit on hold, that the Army had postponed it to Tuesday, Nov. 24."
    ) in when
    assert fs.WHY_WEDNESDAY in when
    assert fs.ARMY_WED_URL in when
    assert fs.COURT_PAUSE in when
    # the court lifted its hold on Nov. 23: nothing may say the permit is still on hold
    assert "on hold by court order" not in llms
    assert "the court lifted its hold on the permit on Nov. 23" in llms
    assert f"- Presidential hold: {fs.TRUMP_HOLD} Sources: {fs.TRUMP_SOURCE_TEXT}" in llms
    assert fs.COURT_PAUSE in llms


def test_wrangler_uses_only_this_projects_credentials() -> None:
    """Shell Cloudflare credentials are dropped; the project's own token is passed on."""
    shell = {"PATH": "/bin", "CLOUDFLARE_API_TOKEN": "other", "CF_API_KEY": "other"}
    env = site.wrangler_env(shell, "acct")
    assert env["CLOUDFLARE_ACCOUNT_ID"] == "acct"
    assert "CLOUDFLARE_API_TOKEN" not in env  # wrangler's own login
    assert "CF_API_KEY" not in env
    assert env["PATH"] == "/bin"
    env = site.wrangler_env({**shell, site.CF_TOKEN_ENV: "ours"}, "acct")
    assert env["CLOUDFLARE_API_TOKEN"] == "ours"  # noqa: S105 - a test value


def _fake_gh(monkeypatch: pytest.MonkeyPatch, returncode: int, stderr: str = "") -> list[list[str]]:
    """Stand in for `gh workflow run` (no network); return the commands it was given."""
    calls: list[list[str]] = []

    def run(cmd: list[str], **_: Any) -> Any:
        calls.append(cmd)
        return type("Done", (), {"returncode": returncode, "stderr": stderr, "stdout": ""})()

    monkeypatch.setattr(site.shutil, "which", lambda _name: "/usr/bin/gh")
    monkeypatch.setattr(site.subprocess, "run", run)
    return calls


def test_mirror_not_started_warns_in_actions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A deploy that can't start the mirror says so on the run, not just in the log."""
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    _fake_gh(monkeypatch, 4, "gh: To use GitHub CLI in a GitHub Actions workflow,\n set GH_TOKEN")
    site.trigger_mirror()
    out = capsys.readouterr().out
    assert out.startswith("::warning title=Mirror not started::")
    assert "set GH_TOKEN" in out
    assert "\n" not in out.strip()  # one annotation line
    assert "MIRROR_DISPATCH_TOKEN" in summary.read_text(encoding="utf-8")


def test_mirror_without_gh(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr(site.shutil, "which", lambda _name: None)
    site.trigger_mirror()
    out = capsys.readouterr().out
    assert out.startswith("note: could not start the mirror build (gh not found)")
    assert "::warning" not in out


def test_mirror_started(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    calls = _fake_gh(monkeypatch, 0)
    site.trigger_mirror()
    assert calls[0][1:] == ["workflow", "run", site.MIRROR_WORKFLOW, "-R", site.MIRROR_REPO]
    out = capsys.readouterr().out
    assert out.startswith("started the GitHub Pages mirror build")
    assert "::warning" not in out


@pytest.mark.slow
def test_public_text_does_not_mention_staged_maps(rendered: tuple[str, list, str]) -> None:
    """The summary, FAQ and llms.txt never point to the staged Wednesday-Friday maps."""
    summary, faq, llms = rendered
    for text in (summary, llms, *(a for _, a in faq)):
        assert not staged.links_to_staged(text)


def test_missing_addresses_get_a_real_page() -> None:
    """A missing address gets 404.html, not a bare 404 iPhone Safari offers to download."""
    assert site.wrangler_config("x")["assets"] == {
        "directory": "./public",
        "not_found_handling": "404-page",
    }
    page = " ".join(site.not_found_page().split())
    assert "<title>Page not found" in page
    assert '<meta name="robots" content="noindex">' in page
    assert '<a href="/">' in page  # works on the main site and the mirror
    assert "This is an unofficial estimate, not from the Army or any government agency." in page
    assert "Don&rsquo;t use it to decide if you&rsquo;re safe." in page
    assert "Follow official instructions." in page
    assert not staged.links_to_staged(page)
    assert "404.html" in site.PUBLISHED_FILES


def test_days_and_map_names() -> None:
    """Only Wednesday (plain names); another day's maps would be prefixed with its date."""
    assert [d for d, _ in site.DAYS] == ["2026-11-25"] == [site.DATE]
    assert set() == site.MENU_ONLY_DAYS  # Thursday was menu-only until Nov. 24
    assert [d for d, _ in site.PAST_DAYS] == ["2026-11-23", "2026-11-24", "2026-11-26"]
    assert site.day_label("2026-11-25") == "Wednesday, Nov. 25"
    assert site.map_name("permit", "12:00") == "permit-1200.html"
    assert site.map_name("permit", "12:00", "2026-11-26") == "2026-11-26-permit-1200.html"
    assert site.map_key("2026-11-26", "low", "11:15") == "2026-11-26-low-1115"
    assert site.day_label("2026-11-26") == "Thursday, Nov. 26"
    assert site.blast_label("12:00", "2026-11-26") == "Thursday, Nov. 26, 2026, 12:00 p.m. CST"


def test_forecast_order_rrfs_then_gfs() -> None:
    """RRFS is shown where it covers the run (Monday); otherwise GFS (Tuesday)."""
    assert site.WEATHER.split(",")[:2] == ["ncep_rrfs_conus", "gfs_global"]


def test_days_to_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A deploy builds only the days its saved forecasts cover; a refresh builds them all."""
    cache = tmp_path / "map_met_all.json"
    monkeypatch.setattr(site, "MET_CACHE", cache)
    assert site.days_to_build() == ["2026-11-25"]  # downloading
    cache.write_text('{"x?start_date=2026-11-25&end_date=2026-11-26": 1}', encoding="utf-8")
    assert site.days_to_build() == ["2026-11-25"]
    cache.write_text(
        '{"a?start_date=2026-11-25&x": 1, "b?start_date=2026-11-26&x": 1}', encoding="utf-8"
    )
    assert site.days_to_build() == ["2026-11-25"]  # saved Thursday forecasts are ignored
    # With a second day configured, it is built only when the saved forecasts cover it.
    monkeypatch.setattr(site, "DAYS", [("2026-11-25", "wed"), ("2026-11-26", "thu")])
    assert site.days_to_build() == ["2026-11-25", "2026-11-26"]
    cache.write_text('{"x?start_date=2026-11-25&end_date=2026-11-26": 1}', encoding="utf-8")
    assert site.days_to_build() == ["2026-11-25"]


def test_page_has_a_day_menu() -> None:
    page = site.PAGE_TEMPLATE.read_text(encoding="utf-8")
    assert '<select id="d">$day_options</select>' in page
    assert "$header_days" in page
    assert "day.value + '-' + cas.value + '-' + t]" in page


@pytest.mark.slow
def test_second_day_in_summary_faq_and_llms(rendered_two_days: tuple[str, list, str]) -> None:
    summary, faq, llms = rendered_two_days
    assert "<h3>If the blasts are on Thursday, Nov. 26</h3>" in summary
    assert summary.index("If the blasts are on Thursday") > summary.index("Lead in the air")
    assert "For noon Thursday the forecast had surface winds" in summary
    assert "from two weather models" in summary  # its own model count
    assert summary.count(fs.TOWN_CAVEAT) >= 2  # the caveat after every list of towns
    answers = dict(faq)
    tue = answers["What if the blasts are on Thursday, Nov. 26?"]
    assert fs.TOWN_CAVEAT in tue
    assert fs.CAVEAT in tue
    assert f"- Thursday, Nov. 26 (also modeled): {fs.SAME_WINDOW}" in llms


@pytest.mark.slow
def test_one_day_has_no_second_day_text(rendered: tuple[str, list, str]) -> None:
    summary, faq, llms = rendered
    assert "If the blasts are on" not in summary
    assert not any(q.startswith("What if the blasts are on") for q, _ in faq)
    assert "also modeled" not in llms


def test_court_paragraph_names_the_days_modeled() -> None:
    """The court paragraph cites the Tuesday filing and names only the days built."""
    assert "emergency exclusion in EPA\u2019s rules to detonate the lead azide without" in (
        fs.COURT_HOLD
    )
    assert fs.WHY_TUESDAY.startswith(
        "In a court filing on Nov. 22, 2026, the government said the Army postponed the "
        "controlled detonation again, to Tuesday, Nov. 24, and intends to act that day."
    )
    assert "The Army\u2019s maps and updates are at" in fs.time_note("X")
    assert f'<a href="{fs.ADVISORY_NOV24_URL}" rel="noopener">{fs.ADVISORY_NOV24_CITE}</a>' in (
        fs.time_note_html("X")
    )
    # no longer "unclear" which day: the Nov. 22 filing says Tuesday
    assert "unclear" not in fs.COURT_HOLD
    assert "had postponed them to Tuesday, Nov. 24" in fs.COURT_HOLD
    assert fs.court_pause().endswith("These maps model Wednesday, Nov. 25.")
    assert fs.court_pause(["Thursday, Nov. 26"]).endswith(
        "These maps model Wednesday, Nov. 25, and Thursday, Nov. 26."
    )
    # the filings are the primary sources, newest first; KCCI is the news report
    assert fs.FILING_URL.startswith("https://s3.documentcloud.org/documents/28930203/")
    assert fs.RESPONSE_URL.endswith("/gov.uscourts.ca8.116088.805661522.0.pdf")
    src = fs.TUESDAY_SOURCES_HTML
    assert src.index(fs.RESPONSE_URL) < src.index(fs.FILING_URL) < src.index(fs.KCCI_URL)
    assert f'href="{fs.RESPONSE_URL}"' in fs.COURT_SOURCES_HTML
    assert any("805661522" in r and "opposition" in r for r in works_cited.REFERENCES)
    assert any("No. 26-3374" in r and "documentcloud" in r for r in works_cited.REFERENCES)
    assert any("kcci.com" in r for r in works_cited.REFERENCES)


@pytest.mark.slow
def test_two_days_court_paragraph(rendered_two_days: tuple[str, list, str]) -> None:
    summary, faq, llms = rendered_two_days
    both = "These maps model Wednesday, Nov. 25, and Thursday, Nov. 26."
    assert both in summary
    assert both in dict(faq)["When was the lead azide blast at the Iowa Army Ammunition Plant?"]
    assert both in llms


def test_about_box_leads_with_when() -> None:
    """The About box opens with the time and official advice and keeps to the essentials.

    The timeline (how the date was set, the court case, earlier dates) and the details
    behind the four cases are in the Methodology and References dialog (Nov. 25, 2026).
    """
    page = site.PAGE_TEMPLATE.read_text(encoding="utf-8")
    about = " ".join(dialog(page, "note").split())
    cite = " ".join(dialog(page, "cite").split())
    first = about.index("About this map</h2>") + len("About this map</h2>")
    assert about[first:].startswith(" $about_time <p><b>Court case.</b>")
    lead = fs.about_time_html("X")
    assert lead.startswith(f"<p><b>{fs.TIME_HEAD}</b> As of this update (X)")
    for part in ("5-mile cone", "shelter in place", "1-800-621-3362", "army.mil/asc"):
        assert part in lead
    assert lead.index("1-800-621-3362") < lead.index("army.mil/asc")  # help before maps

    # the same sentences as the FAQ's and llms.txt's time paragraph, only split up
    def plain(html_text: str) -> str:
        return " ".join(re.sub(r"<[^>]+>|<p>|</p>", " ", html_text).split())

    about_text = plain(re.sub(r"<b>[^<]*</b>", "", lead))
    for sentence in plain(fs.time_note_html("X")).split(". "):
        assert sentence in about_text
    heads = [
        "<b>Court case.</b>",
        "<b>What the map shows.</b>",
        "<b>Don&rsquo;t use this map to decide if you&rsquo;re safe.</b>",
        "<b>Who made it.</b> $about_who",
        "<b>Contact.</b>",
        "<b>Privacy.</b>",
    ]
    assert [about.index(h) for h in heads] == sorted(about.index(h) for h in heads)
    history = (
        "<b>How the date was set.</b> $trump_hold Sources: $trump_source. $why_wednesday "
        "Source: $wednesday_source.</p>"
    )
    for moved in (history, "$why_tuesday", "$precedent", "$misting", "$release_point"):
        assert moved not in about
        assert moved in cite
    assert cite.index(history) < cite.index("<b>Court case.</b> $court_pause")
    assert "<b>$earlier_head</b> $why_tuesday Sources: $tuesday_sources. $why_monday" in cite
    assert cite.index("$why_monday") < cite.index("$cite_html")
    assert fs.TIME_HEAD == "When."
    note = fs.time_note("X")
    assert note.startswith(
        "As of this update (X), the Army carried out the controlled detonation at 9:00 a.m. "
        "CST on Wednesday, Nov. 25. In its 3 p.m. CST update, which gives that time, the Army "
        "said air sensors report no lead detection "
        "at this time, and that sampling of the ground after the detonation is underway, with "
        "results to be published when available (Army maps, Nov. 25, 3 p.m.). "
    )
    resume = " On Wednesday evening, Middletown\u2019s city clerk said the Army, CDC, EPA and"
    assert f"{fs.EARLY_AIR}{resume} FEMA had confirmed normal activities could resume" in note
    assert note.count("Follow official instructions.") == 1


def test_blast_status_says_to_wait_for_the_army() -> None:
    """The reported blast is attributed, linked, and points readers to the Army's results."""
    for text in (fs.BLAST_DONE, fs.BLAST_STATUS_HTML):
        plain = text.replace("<b>", "").replace("</b>", "")
        assert "confirmed normal activities could resume" in plain  # attributed, not ours
        assert "Middletown" in plain
        assert "city clerk" in plain
        assert "Follow official instructions." in plain
        assert "no lead detection at this time" in text
        assert "safe" not in text.lower()  # no verdicts about anyone's safety
    for text in (fs.BLAST_DONE, fs.BLAST_STATUS_HTML):
        assert "9:00 a.m. CST" in text  # the time from the Army's 3 p.m. maps
    assert fs.ARMY_3PM_URL in fs.BLAST_STATUS_HTML
    assert fs.ARMY_3PM_URL in fs.time_note_html("X")
    assert any(r.startswith("McFate, L., 2026d:") for r in works_cited.REFERENCES)
    assert fs.CBS2_RESUME_URL in fs.BLAST_STATUS_HTML
    assert fs.CBS2_RESUME_URL in fs.time_note_html("X")
    assert any(r.startswith("Iowa&rsquo;s News Now, 2026:") for r in works_cited.REFERENCES)
    assert "FEMA evacuation (Nov. 24):" in fs.FEMA_HEADER_HTML  # dated, not current advice
    assert "Before the blast, FEMA supported relocating" in fs.time_note("X")
    assert "191 square miles" in fs.time_note("X")  # the Army's latest maps, not Nov. 24's
    assert any(r.startswith("McFate, L., 2026c:") for r in works_cited.REFERENCES)


def test_observed_weather_at_blast_time() -> None:
    """Airport weather at 9 a.m. is given beside the model's, attributed and linked."""
    assert "northeast at about 9 mph and clear skies" in fs.OBSERVED_WX
    assert fs.IEM_CITE in fs.OBSERVED_WX
    assert "12,000 feet" in fs.OBSERVED_SKY
    assert (fs.IEM_CITE, fs.IEM_URL) in fs.NAMED_SOURCES
    assert any(r.startswith("Iowa Environmental Mesonet, 2026:") for r in works_cited.REFERENCES)


def test_early_air_readings_say_lab_results_are_pending() -> None:
    """Early EPA readings are attributed, linked, and say more sampling is still needed."""
    for text in (fs.EARLY_AIR, fs.EARLY_AIR_HTML):
        assert "early readings only" in text.lower()
        assert "still pending and are needed" in text.replace("</b>", "")
        assert "soil and water sampling" in text
        assert "safe" not in text.lower()  # no verdicts about anyone's safety
    assert fs.EARLY_AIR in fs.time_note("X")
    assert fs.EPA_VIEWER_URL in fs.EARLY_AIR_HTML
    assert fs.EPA_VIEWER_URL in fs.time_note_html("X")
    assert any(r.startswith("EPA Region 7, 2026:") for r in works_cited.REFERENCES)
    assert any(r.startswith("New York Times, 2026:") for r in works_cited.REFERENCES)


def test_window_words_match_the_blast_times() -> None:
    """The page's blast-time words match the times each site builds.

    The main site models 9 a.m. only since Nov. 26; the staged page keeps its window.
    """
    assert site.TIMES == ["09:00"]
    assert fs.BLAST_TIME == "9 a.m."
    assert f"a blast at {fs.BLAST_TIME}, the time the Army had set." in fs.time_note("X")
    assert [site.label(t) for t in (staged.TIMES[0], staged.TIMES[-1])] == [
        "8:30 a.m.",
        "9:30 a.m.",
    ]
    assert fs.WINDOW == "8:30 to 9:30 a.m."
    assert fs.WINDOW_HOURLY == "at 8:30, 9:00 and 9:30 a.m."
    assert staged.TIMES == ["08:30", "09:00", "09:30"]
    assert site.DEFAULT in site.TIMES
    assert staged.DEFAULT_TIME in staged.TIMES


@pytest.mark.slow
def test_summary_why_section_cites_both(rendered: tuple[str, list, str]) -> None:
    summary, faq, llms = rendered
    assert "<h3>When was the detonation?</h3>" in summary
    assert fs.WHY_TUESDAY in summary
    assert fs.TUESDAY_SOURCES_HTML in summary
    assert (
        fs.WHY_TUESDAY
        in dict(faq)["When was the lead azide blast at the Iowa Army Ammunition Plant?"]
    )
    assert f"- Earlier date, Tuesday: {fs.WHY_TUESDAY} Sources: {fs.TUESDAY_SOURCES_TEXT}" in llms


@pytest.mark.slow
def test_two_days_label_monday_and_keep_notes(rendered_two_days: tuple[str, list, str]) -> None:
    """With a second day, the lead day's parts say Wednesday and each day keeps its notes."""
    summary, faq, llms = rendered_two_days
    for h in ("Where the cloud goes", "How far lead on the ground could reach", "Lead in the air"):
        assert f"<h3>{h} on Wednesday, Nov. 25</h3>" in summary
    # Wednesday's permit weather stays with the Army comparison, before the Thursday section
    assert (
        summary.index("For noon Wednesday the forecast")
        < summary.index("If the blasts are on Thursday")
        < summary.index("For noon Thursday the forecast")
    )
    thu = summary[summary.index("If the blasts are on Thursday") :]
    assert fs.REACH_NOTE in thu
    assert fs.SAME_WINDOW in thu
    assert "actual\n    winds may have differed from the forecast" in summary
    assert "before Wednesday" not in summary
    answers = dict(faq)
    assert answers["Where could the lead go?"].startswith("For Wednesday, Nov. 25: ")
    assert fs.REACH_NOTE in answers["What if the blasts are on Thursday, Nov. 26?"]
    assert "- Wednesday, Nov. 25: Forecast pulled" in llms


def _fake_map(models: list[str]) -> str:
    return '{"airborneFraction": 0.07, "models":' + json.dumps(models) + "}"


def test_read_maps_days_and_model_counts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A day missing any blast time is left out; each day counts its own models."""
    monkeypatch.setattr(site, "MAPS", tmp_path)
    # The multi-day machinery, with Thursday configured as it was until Nov. 24.
    monkeypatch.setattr(site, "DAYS", [("2026-11-25", "wed"), ("2026-11-26", "thu")])
    four = site.WEATHER.split(",")
    thu = "2026-11-26"
    for c, _, _ in site.CASES:
        for t in site.TIMES:
            (tmp_path / site.map_name(c, t)).write_text(_fake_map(four), encoding="utf-8")
            if t != site.TIMES[-1]:  # Thursday is missing one time
                (tmp_path / site.map_name(c, t, thu)).write_text(
                    _fake_map(four[:3]), encoding="utf-8"
                )
    maps = site.read_maps()
    assert list(maps.days) == ["2026-11-25"]  # partly built Thursday left out
    assert site.lead_day(maps) == site.DATE == site.LEAD_DAY  # opens on Wednesday
    for c, _, _ in site.CASES:
        (tmp_path / site.map_name(c, site.TIMES[-1], thu)).write_text(
            _fake_map(four[:3]), encoding="utf-8"
        )
    maps = site.read_maps()
    assert list(maps.days) == ["2026-11-25", thu]
    assert maps.days[thu] == site.TIMES
    assert site.lead_day(maps) == "2026-11-25"  # still Wednesday
    assert site.model_count(maps.pages_by_day["2026-11-25"]) == "four"
    assert site.model_count(maps.pages_by_day[thu]) == "three"


def test_remove_days_not_built(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(site, "MAPS", tmp_path)
    (tmp_path / "permit-1200.html").write_text("mon", encoding="utf-8")
    (tmp_path / "2026-11-24-permit-1200.html").write_text("old tue", encoding="utf-8")
    site.remove_days_not_built(["2026-11-24", "2026-11-23"])
    assert (tmp_path / "2026-11-24-permit-1200.html").exists()
    site.remove_days_not_built(["2026-11-23"])
    assert not (tmp_path / "2026-11-24-permit-1200.html").exists()
    assert (tmp_path / "permit-1200.html").exists()  # the planned day is never removed
    # a dropped day's maps go too, even though DAYS no longer lists it
    (tmp_path / "2026-11-24-low-1100.html").write_text("dropped", encoding="utf-8")
    (tmp_path / "2026-11-26-low-1100.html").write_text("thu", encoding="utf-8")
    site.remove_days_not_built(["2026-11-25", "2026-11-26"])
    assert not (tmp_path / "2026-11-24-low-1100.html").exists()
    assert (tmp_path / "2026-11-26-low-1100.html").exists()


def test_page_opens_on_the_lead_day_and_old_links_keep_monday() -> None:
    page = site.PAGE_TEMPLATE.read_text(encoding="utf-8")
    assert "const DAY_CODES = $day_codes, LINK_DAY = $link_day, OPEN_DAY = $open_day;" in page
    assert "const want = found || (ht && !hd ? LINK_DAY : OPEN_DAY);" in page
    assert "(day.value === LINK_DAY ? '' : '-' + DAY_CODES[day.value])" in page
    assert "FIRST_DAY" not in page


def test_link_to_a_day_not_in_this_update_says_so() -> None:
    page = site.PAGE_TEMPLATE.read_text(encoding="utf-8")
    assert '<p class="daynote" id="daynote" role="status" hidden></p>' in page
    assert "const ALL_DAYS = $all_days;" in page
    assert "maps aren\\u2019t in this update; showing " in page


def test_long_links_wrap_on_phones() -> None:
    """Source URLs shown as link text (the court filing) mustn't push the page sideways."""
    css = site.PAGE_TEMPLATE.read_text(encoding="utf-8")
    assert re.search(r"\.doc a \{[^}]*overflow-wrap: anywhere", css)
    assert re.search(r"dialog a \{[^}]*overflow-wrap: anywhere", css)


def test_refresh_pr_text_finds_the_path_section(
    rendered: tuple[str, list, str], rendered_two_days: tuple[str, list, str]
) -> None:
    """The refresh quotes "Where the cloud goes" in its PR; the heading gains a day."""
    root = Path(__file__).resolve().parent.parent
    workflow = (root / ".github/workflows/refresh-forecast.yml").read_text(encoding="utf-8")
    m = re.search(r'page\.find\("([^"]+)"\)', workflow)
    assert m
    for summary, _, _ in (rendered, rendered_two_days):
        assert m.group(1) in summary
    assert "<h3>Where the cloud goes on Wednesday, Nov. 25</h3>" in rendered_two_days[0]


def test_four_weather_models_and_hrrr_first_near_the_blast() -> None:
    """RRFS leads a day or more out; HRRR leads within 18 hours; four models in all."""
    assert site.WEATHER.split(",") == [
        "ncep_rrfs_conus",
        "gfs_global",
        "ncep_hrrr_conus",
        "ecmwf_ifs025",
    ]
    assert sorted(site.WEATHER_SHORT_RANGE.split(",")) == sorted(site.WEATHER.split(","))
    assert site.WEATHER_SHORT_RANGE.startswith("ncep_hrrr_conus,")
    blast = dt.datetime.fromisoformat("2026-11-24T12:00-06:00")
    early = dt.datetime.fromisoformat("2026-11-23T10:00-06:00")  # 26 hours ahead
    late = dt.datetime.fromisoformat("2026-11-23T18:00-06:00")  # 18 hours ahead
    assert site.weather_for(blast, early) == site.WEATHER
    assert site.weather_for(blast, late) == site.WEATHER_SHORT_RANGE
    assert site.MODEL_ARGS[site.MODEL_ARGS.index("--weather-model") + 1] == site.WEATHER


def test_coverage_check_counts_only_the_run_hours() -> None:
    """A model that stops after the run (HRRR's 48-hour runs) isn't skipped any more."""
    times = [f"2026-11-24T{h:02d}:00" for h in range(24)] + [
        f"2026-11-25T{h:02d}:00" for h in range(24)
    ]
    ws = [3.0] * 30 + [None] * 18  # data until 2026-11-25 05:00 UTC, then nothing
    data = {"hourly": {"time": times, "wind_speed_10m": ws}}
    utc = dt.timezone.utc
    start = dt.datetime(2026, 11, 24, 17, tzinfo=utc)  # 11 a.m. CST
    end = dt.datetime(2026, 11, 25, 2, tzinfo=utc)  # the 8-hour run and a margin
    assert met._data_problem(data) == "data missing for the requested period"  # whole days
    assert met._data_problem(data, start, end) is None  # just the run
    gap = {"hourly": {"time": times, "wind_speed_10m": [3.0] * 18 + [None] * 30}}
    assert met._data_problem(gap, start, end) == "data missing for the requested period"


@pytest.fixture(scope="module")
def rendered_wednesday_lead(
    facts_ctx: tuple[dict[str, Any], dict[str, Any]],
) -> tuple[str, list, str]:
    """Render with Wednesday leading, then Monday and Tuesday (earlier planned dates)."""
    facts, ctx = facts_ctx
    days = [fs.HHS_DAY, "Tuesday, Nov. 24", "Wednesday, Nov. 25"]
    by = {d: {**facts, "day": d, "n_models": "one"} for d in days}
    return fs.render(by[days[2]], ctx, [by[days[0]], by[days[1]]])


@pytest.mark.slow
def test_wednesday_leads(rendered_wednesday_lead: tuple[str, list, str]) -> None:
    summary, faq, llms = rendered_wednesday_lead
    assert "<h3>Where the cloud goes on Wednesday, Nov. 25</h3>" in summary
    assert fs.window_note("Wednesday, Nov. 25") == ""  # TIME_HEAD's paragraph covers it
    for d in ("Monday, Nov. 23", "Tuesday, Nov. 24"):
        assert f"<h3>{d}, an earlier planned date</h3>" in summary
    assert summary.index("Wednesday, Nov. 25</h3>") < summary.index("Monday, Nov. 23, an")
    assert "These maps model Monday, Nov. 23, Tuesday, Nov. 24, and Wednesday, Nov. 25." in summary
    assert fs.WHY_WEDNESDAY in summary
    assert fs.WEDNESDAY_SOURCE_HTML in summary
    assert "Late on Nov. 22, the Army said the blasts are now scheduled for Wednesday" in summary
    # newest first: the Nov. 23 ruling, then Wednesday, Tuesday and Monday
    assert fs.COURT_HOLD.startswith(
        "On Monday, Nov. 23, 2026, the 8th U.S. Circuit Court of Appeals cleared the way"
    )
    assert fs.COURT_HOLD.index("cleared the way") < fs.COURT_HOLD.index("Late on Nov. 22")
    assert fs.COURT_HOLD.index("Tuesday, Nov. 24") < fs.COURT_HOLD.index("Late on Nov. 19")
    # newest first: the Army Secretary's post that evening, then the ruling
    assert fs.COURT_SOURCES_HTML.startswith(f'<a href="{fs.SECARMY_URL}"')
    assert fs.COURT_SOURCES_HTML.index(fs.SECARMY_URL) < fs.COURT_SOURCES_HTML.index(fs.RULING_URL)
    assert "Sand" not in fs.COURT_HOLD
    assert "cleared the way for the detonation (see Court case)" in fs.TRUMP_HOLD
    assert f'href="{fs.SAND_URL}"' in fs.COURT_SOURCES_HTML
    when = summary[summary.index("When was the detonation?") :]
    assert when.index(fs.WHY_WEDNESDAY) < when.index(fs.WHY_TUESDAY) < when.index(fs.WHY_MONDAY)
    why = [
        llms.index(k)
        for k in (
            "- Time and official advice:",
            "- Why Wednesday:",
            "- Earlier date, Tuesday:",
            "- Earlier date, Mon",
        )
    ]
    assert why == sorted(why)  # the key facts first, then how the date was set
    assert "<p><b>Earlier dates.</b> " in summary
    assert "on Monday, Nov. 23, Tuesday, Nov. 24, Wednesday, Nov. 25." in llms
    assert "What would the map show for Tuesday, Nov. 24, an earlier planned date?" in dict(faq)


def _maps_for(days: list[str]) -> site.Maps:
    """Return a Maps with the given days built (no files needed for the day values)."""
    return site.Maps(
        pages=[],
        pct={},
        times=site.TIMES,
        default=site.DEFAULT,
        days=dict.fromkeys(days, site.TIMES),
        pages_by_day={d: [] for d in days},
    )


def test_day_values_wednesday_only() -> None:
    """Only Wednesday: no Day menu; an old Thursday link says it isn't in this update."""
    v = site.day_values(_maps_for(["2026-11-25"]), "2026-11-25")
    assert v["day_hidden"] == " hidden"
    assert v["header_days"] == "Wednesday, Nov. 25"
    assert json.loads(v["day_codes"]) == {"2026-11-25": "wed"}
    assert json.loads(v["all_days"])["thu"] == "Thursday, Nov. 26"


def test_day_values_wednesday_with_thursday_in_the_menu_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wednesday leads; Thursday is a Day menu option but not in the header."""
    monkeypatch.setattr(site, "DAYS", [("2026-11-25", "wed"), ("2026-11-26", "thu")])
    monkeypatch.setattr(site, "MENU_ONLY_DAYS", {"2026-11-26"})
    maps = _maps_for(["2026-11-25", "2026-11-26"])
    lead = site.lead_day(maps)
    v = site.day_values(maps, lead)
    assert lead == "2026-11-25"
    assert v["header_lead"] == "Lead from the blast at the Iowa Army Ammunition Plant"
    assert v["header_days"] == "Wednesday, Nov. 25"  # no "also modeled: Thursday"
    assert v["pending_note"] == ""
    assert v["pending_hidden"] == " hidden"
    assert '<option value="2026-11-25" selected>Wednesday, Nov. 25</option>' in v["day_options"]
    assert '<option value="2026-11-26">Thursday, Nov. 26</option>' in v["day_options"]
    assert v["day_hidden"] == ""  # the menu shows
    assert v["open_day"] == v["link_day"] == '"2026-11-25"'
    assert json.loads(v["day_codes"]) == {"2026-11-25": "wed", "2026-11-26": "thu"}
    # an old Monday or Tuesday link says that day isn't modeled, by name
    assert json.loads(v["all_days"])["tue"] == "Tuesday, Nov. 24"
    page = site.PAGE_TEMPLATE.read_text(encoding="utf-8")
    assert "<p>$header_lead, $header_days</p>" in page
    assert '<p class="daynote" id="pendingnote"$pending_hidden>$pending_note</p>' in page
    assert "Nov. 25" not in site.DESCRIPTION_NO_DATE
    # Wednesday is always built, so the "not in this update" note never shows
    assert site.pending_note(site.DATE) == ""


def test_one_model_order_per_day(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A day's maps never mix HRRR and RRFS, even when 18 hours falls inside the window."""
    cache = tmp_path / "met.json"
    cache.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(site, "MET_CACHE", cache)
    monkeypatch.setattr(site, "MAPS", tmp_path / "maps")
    monkeypatch.setattr(site.staged, "CACHE", tmp_path / "none.json")
    monkeypatch.setattr(site, "days_to_build", lambda: ["2026-11-25"])
    # 3:40 p.m. CST Tuesday: 9:00 Wednesday (the default) is 17.3 h away, 10:00 18.3 h
    pulled = dt.datetime.fromisoformat("2026-11-24T15:40-06:00")
    monkeypatch.setattr(site, "retrieved_at", lambda *_a, **_k: pulled)
    orders = set()

    class Done:
        returncode = 0
        stdout = stderr = ""

    def fake_run(cmd: list[str], **_: object) -> Done:
        if "archived" not in cmd[cmd.index("-o") + 1]:  # the forecast maps
            orders.add(cmd[cmd.index("--weather-model") + 1])
        return Done()

    monkeypatch.setattr(site.subprocess, "run", fake_run)
    site.build()
    # one order for the whole day, picked at the default 9:00 (under 18 h out): HRRR first
    assert orders == {site.WEATHER_SHORT_RANGE}


def test_president_and_governor_elect_after_the_ruling() -> None:
    """The Nov. 23 ruling and Sand's reply, quoted as Iowa Public Radio reported them."""
    assert (
        "\u201cthe Administration should make this decision based on the information they have "
        "from the people they brought in to do the job months ago and have been on the ground "
        "in Middletown for weeks.\u201d"
    ) in fs.TRUMP_HOLD
    assert "didn\u2019t directly say whether he approved" in fs.TRUMP_HOLD
    for url in (fs.TRUMP_URL, fs.RULING_URL, fs.SAND_URL):
        assert url in fs.TRUMP_SOURCE_TEXT
    assert (fs.SAND_CITE, fs.SAND_URL) in fs.CITED_SOURCES
    assert (fs.RULING_CITE, fs.RULING_URL) in fs.CITED_SOURCES


def test_mentions_in_methodology() -> None:
    """News mentions sit in Methodology and References (not About) and link the outlet."""
    page = site.PAGE_TEMPLATE.read_text(encoding="utf-8")
    assert "$mentions_html" not in dialog(page, "note")
    assert "<p><b>$mentions_head</b> $mentions_html</p>" in dialog(page, "cite")
    assert works_cited.MENTIONS_HEAD == "Mentions of the Iowa Lead Tracker."
    for outlet, date, url in works_cited.MENTIONS:
        assert f'<a href="{url}" rel="noopener">{outlet}</a>, {date}' in works_cited.MENTIONS_HTML
        assert "yahoo.com" not in url  # the original publisher, not a syndicated copy


def test_methodology_and_references_dialog() -> None:
    """The dialog is "Methodology and References" and opens with a short note on the method."""
    page = site.PAGE_TEMPLATE.read_text(encoding="utf-8")
    assert '<h2 id="cite-h" tabindex="-1" autofocus>Methodology and References</h2>' in page
    assert 'aria-haspopup="dialog">Methodology and References</button>' in page
    pct = {"low": "7%", "mid": "26%", "high": "55%", "permit": "100%"}
    ctx = {
        "pct": pct,
        "n_models": "two",
        "got_txt": "November 23, 2026, at 2:34 p.m. CST",
        "shown_model": "GFS",
        "models": [],
    }
    body = works_cited.render(ctx, "https://example.org/", "now")
    assert body.lstrip().startswith(f"<p><b>{works_cited.METHOD_HEAD}</b> ")
    note = works_cited.method_intro(pct)
    assert note in body
    assert body.index(note) < body.index("<h3>References</h3>") < body.index("Key assumptions")
    assert '<a href="https://narac.llnl.gov/hotspot" rel="noopener">HotSpot</a>' in note
    for part in ("Gaussian puff", "71.1%", "6,900 lb", "Church (1969)", "100%, which EPA"):
        assert part in note
    assert "55% (high), 26% (U.S. Army mitigated) and 7% (low)" in note


def test_change_log_follows_the_method_note() -> None:
    """A dated change log sits right after the method note, newest first, with the spread switch."""
    pct = {"low": "7%", "mid": "26%", "high": "55%", "permit": "100%"}
    ctx: dict[str, Any] = {
        "pct": pct,
        "n_models": "two",
        "got_txt": "now",
        "shown_model": "GFS",
        "models": [],
    }
    body = works_cited.render(ctx, "https://example.org/", "now")
    head = f"<h3>{works_cited.CHANGES_HEAD}</h3>"
    assert body.index(works_cited.method_intro(pct)) < body.index(head)
    assert body.index(head) < body.index("<h3>References</h3>")
    days = [int(when.split()[-1]) for when, _ in works_cited.CHANGES]
    assert days == sorted(days, reverse=True)
    assert any(
        "turbulence" in what and works_cited.TURBULENCE_URL in what
        for _, what in works_cited.CHANGES
    )
    assert "change log" in works_cited.method_intro(pct)


def test_site_maps_use_the_turbulence_spread() -> None:
    """The public and staged maps pass --spread turbulence (TURBULENCE.md)."""
    for args in (site.MODEL_ARGS, staged.model_args()):
        assert args[args.index("--spread") + 1] == "turbulence"


def test_saved_forecasts_without_temperature_get_the_fallback(tmp_path: Path) -> None:
    """Old saved forecasts replay offline with a fixed temperature; new ones use their own."""
    old = tmp_path / "old.json"
    old.write_text('{"https://x/?hourly=wind_speed_10m": {}}', encoding="utf-8")
    new = tmp_path / "new.json"
    new.write_text('{"https://x/?hourly=wind_speed_10m,temperature_2m": {}}', encoding="utf-8")
    assert site.temperature_args(old) == ["--air-temperature-c", site.FALLBACK_AIR_TEMPERATURE_C]
    assert site.temperature_args(new) == []
    assert site.temperature_args(tmp_path / "missing.json") == []  # a refresh downloads it


def test_time_note_gives_the_official_advice() -> None:
    """The 9 a.m. time comes with the Army's and FEMA's own advice, attributed and linked."""
    note = fs.time_note("X")
    for part in ("5-mile cone extending southwest", "shelter in place", "1-800-621-3362"):
        assert part in note
    assert fs.ADVISORY_NOV24_URL in fs.time_note_html("X")
    assert any(r.startswith("McFate, L., 2026b:") for r in works_cited.REFERENCES)
    assert site.DEFAULT == staged.DEFAULT_TIME == "09:00"
    assert any(r.startswith("FEMA, 2026:") for r in works_cited.REFERENCES)


def test_build_switch_matches_the_model() -> None:
    """The build's cache-only switch and exit status are the model's."""
    assert site.CACHE_ONLY_ENV == met.CACHE_ONLY_ENV
    assert site.NOT_SAVED_EXIT == met.NOT_SAVED_EXIT
    assert not issubclass(met.NotSaved, Exception)  # the per-model fallbacks can't catch it


def test_run_maps_skips_times_without_saved_forecasts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With saved forecasts, downloads are off; a time not saved is skipped, its old map gone."""
    seen: list[dict[str, str] | None] = []

    class Done:
        def __init__(self, code: int) -> None:
            self.returncode = code
            self.stdout = self.stderr = ""

    def fake_run(cmd: list[str], **kw: Any) -> Done:
        seen.append(kw.get("env"))
        return Done(site.NOT_SAVED_EXIT if "08:30" in cmd else 0)

    monkeypatch.setattr(site.subprocess, "run", fake_run)
    old = tmp_path / "permit-0830.html"
    old.write_text("stale", encoding="utf-8")
    runs = [
        site.Run("permit 08:30", ["08:30"], old),
        site.Run("permit 09:00", ["09:00"], tmp_path / "permit-0900.html"),
    ]
    assert site.run_maps(runs, saved=True) == ["permit 08:30"]
    assert not old.exists()  # the page then leaves 8:30 out (complete_times)
    assert all(env and env[site.CACHE_ONLY_ENV] == "1" for env in seen)
    assert all(env and env["OPENBLAS_NUM_THREADS"] == "1" for env in seen)  # no oversubscription
    seen.clear()
    with pytest.raises(SystemExit):  # downloading (a refresh): any failure stops the build
        site.run_maps(runs, saved=False)
    assert len(seen) == 1  # the first run failed; nothing ran after it
    assert seen[0] is not None
    assert site.CACHE_ONLY_ENV not in seen[0]  # it could download
    assert seen[0]["OPENBLAS_NUM_THREADS"] == "1"  # every run is made the same way


class _Done:
    def __init__(self, code: int = 0) -> None:
        self.returncode = code
        self.stdout = ""
        self.stderr = f"exit {code}" if code else ""


def _runs(tmp_path: Path, times: list[str], cases: list[str]) -> list[site.Run]:
    """Return runs for ``times`` (``2026-11-25T09:00``) x ``cases``, each with its own map."""
    return [
        site.Run(
            f"{case} {t}",
            ["--time", f"{t}-06:00", f"{case}-{t}"],
            tmp_path / f"{case}-{t.replace(':', '')}.html",
        )
        for t in times
        for case in cases
    ]


def _fake_model(
    monkeypatch: pytest.MonkeyPatch, codes: dict[str, int] | None = None
) -> list[tuple[str, bool]]:
    """Patch the model runs; return the (run, downloads off) list they fill in.

    ``codes`` gives a run's exit status when downloads are off (else 0).
    """
    ran: list[tuple[str, bool]] = []

    def fake_run(cmd: list[str], **kw: Any) -> _Done:
        env = kw["env"]
        assert env["OPENBLAS_NUM_THREADS"] == "1"  # every run, downloading or not
        cache_only = site.CACHE_ONLY_ENV in env
        ran.append((cmd[-1], cache_only))
        return _Done((codes or {}).get(cmd[-1], 0) if cache_only else 0)

    monkeypatch.setattr(site.subprocess, "run", fake_run)
    return ran


def test_refresh_downloads_one_run_per_hour_then_runs_the_rest_at_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A refresh downloads one run per start hour at a time, then runs the rest at once.

    The rest have downloads off; one that still needs a download runs again and gets it.
    """
    # the high case at 9:30 needs something the low case didn't download
    ran = _fake_model(monkeypatch, {"high-2026-11-25T09:30": site.NOT_SAVED_EXIT})
    times = ["2026-11-25T08:30", "2026-11-25T09:00", "2026-11-25T09:30"]
    runs = _runs(tmp_path, times, ["low", "high"])
    for r in runs:
        r.out.write_text("old map", encoding="utf-8")
    assert site.run_maps(runs, saved=False) == []
    # 8:30 and 9:00 are two start hours (9:30 shares 9:00's), downloaded one at a time
    assert ran[:2] == [("low-2026-11-25T08:30", False), ("low-2026-11-25T09:00", False)]
    assert sorted(ran[2:6]) == [
        ("high-2026-11-25T08:30", True),
        ("high-2026-11-25T09:00", True),
        ("high-2026-11-25T09:30", True),
        ("low-2026-11-25T09:30", True),
    ]
    assert ran[6:] == [("high-2026-11-25T09:30", False)]  # downloaded after, not skipped
    assert all(r.out.exists() for r in runs)  # a refresh removes no map


def test_refresh_keeps_the_same_hour_on_two_days_apart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """9:00 on Wednesday and on Thursday are different forecasts: each downloads its own."""
    ran = _fake_model(monkeypatch)
    times = ["2026-11-25T09:00", "2026-11-26T09:00"]
    site.run_maps(_runs(tmp_path, times, ["low", "high"]), saved=False)
    assert ran[:2] == [("low-2026-11-25T09:00", False), ("low-2026-11-26T09:00", False)]
    assert all(cache_only for _, cache_only in ran[2:])


def test_refresh_skips_hours_already_downloaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With ``downloaded``, no run for that hour goes alone: they all run at once."""
    ran = _fake_model(monkeypatch)
    times = ["2026-11-25T08:30", "2026-11-25T09:00"]
    site.run_maps(
        _runs(tmp_path, times, ["low", "high"]), saved=False, downloaded=["2026-11-25T08"]
    )
    assert ran[0] == ("low-2026-11-25T09:00", False)  # only 9:00 downloads
    assert sorted(ran[1:]) == [
        ("high-2026-11-25T08:30", True),
        ("high-2026-11-25T09:00", True),
        ("low-2026-11-25T08:30", True),
    ]


def test_refresh_stops_on_a_failure_among_the_runs_at_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A run that fails for any other reason stops the refresh; nothing downloads after it."""
    ran = _fake_model(monkeypatch, {"high-2026-11-25T09:00": 1})
    runs = _runs(tmp_path, ["2026-11-25T09:00"], ["low", "mid", "high"])
    with pytest.raises(SystemExit, match="model run failed for high 2026-11-25T09:00"):
        site.run_maps(runs, saved=False)
    assert all(cache_only for _, cache_only in ran[1:])  # no rerun with downloads


def test_runs_without_a_time_each_download(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A run without ``--time`` is its own group, so each one downloads, one at a time."""
    ran = _fake_model(monkeypatch)
    runs = [site.Run(n, [n], tmp_path / f"{n}.html") for n in ("a", "b")]
    assert site.start_hour(runs[0]) == "a"
    site.run_maps(runs, saved=False)
    assert ran == [("a", False), ("b", False)]


def test_skipped_maps_go_as_each_run_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A map without a saved forecast is removed as soon as its run reports.

    So a later failure doesn't leave it behind.
    """
    _fake_model(
        monkeypatch,
        {"low-2026-11-25T08:30": site.NOT_SAVED_EXIT, "high-2026-11-25T09:00": 1},
    )
    monkeypatch.setattr(site, "PARALLEL_RUNS", 1)  # report in order: 8:30 before the failure
    runs = _runs(tmp_path, ["2026-11-25T08:30", "2026-11-25T09:00"], ["low", "high"])
    for r in runs:
        r.out.write_text("old map", encoding="utf-8")
    with pytest.raises(SystemExit):
        site.run_maps(runs, saved=True)
    assert not runs[0].out.exists()


def test_cache_only_runs_never_download(monkeypatch: pytest.MonkeyPatch) -> None:
    """With the switch set, a request that isn't saved stops the run instead of downloading."""
    monkeypatch.setenv(met.CACHE_ONLY_ENV, "1")
    monkeypatch.setitem(met.MET_CACHE, "path", None)
    with pytest.raises(met.NotSaved):
        met.http_json("https://api.open-meteo.com/v1/forecast?latitude=0")


def _labeled_runs(tmp_path: Path) -> list[site.Run]:
    """Return runs labeled as build() labels them: the planned day without its date."""
    runs = []
    for day in (site.DATE, "2026-11-26"):
        for t in ("08:30", "09:00"):
            for case in ("low", "permit"):
                which = f"{case} {t}" if day == site.DATE else f"{day} {case} {t}"
                cmd = ["--time", f"{day}T{t}-06:00"]
                runs.append(site.Run(which, cmd, tmp_path / f"{day}-{case}-{t}.html"))
    return runs


def test_a_new_time_may_be_skipped_until_the_next_refresh(tmp_path: Path) -> None:
    """Every map of a start hour skipped (a time added since the refresh) is allowed."""
    runs = _labeled_runs(tmp_path)
    site.check_skipped(runs, [r.which for r in runs if r.which.endswith("08:30")])


def test_some_maps_of_one_hour_skipped_stops_the_build(tmp_path: Path) -> None:
    """Some maps of one start hour built and others skipped: the saved forecasts are broken."""
    runs = _labeled_runs(tmp_path)
    with pytest.raises(SystemExit, match="only some maps built: 2026-11-26T08"):
        site.check_skipped(runs, ["2026-11-26 low 08:30"])


def test_the_default_time_skipped_stops_the_build(tmp_path: Path) -> None:
    """The planned day's default time skipped would leave the page without its first map."""
    runs = _labeled_runs(tmp_path)
    gone = [r.which for r in runs if r.which in ("low 09:00", "permit 09:00")]
    with pytest.raises(SystemExit, match="default-time maps skipped: low 09:00, permit 09:00"):
        site.check_skipped(runs, gone)
    # another day's 9:00 alone is a whole start hour, so it may wait for the refresh
    site.check_skipped(runs, [r.which for r in runs if r.which.startswith("2026-11-26")])


def test_about_safety_paragraph_says_no_warranty_and_no_verdicts() -> None:
    """The safety paragraph: not official or checked, no verdicts, warranty, or liability."""
    about = " ".join(dialog(site.PAGE_TEMPLATE.read_text(encoding="utf-8"), "note").split())
    i = about.index("<b>Don&rsquo;t use this map to decide if you&rsquo;re safe.</b>")
    para = about[i : about.index("</p>", i)]
    for part in (
        "$not_checked",
        "can&rsquo;t tell you whether any particular home or place will get lead",
        "It comes with no warranty",
        "Its maker isn&rsquo;t responsible for any loss or harm from using it",
        "follow $who",
    ):
        assert part in para
