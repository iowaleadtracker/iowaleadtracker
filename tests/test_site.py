"""The site's safety wording and settings can't silently disappear.

The warnings ("unofficial", "not from the Army", "don't use it to decide if you're
safe", the caveat after every town list) are the project's main protection against
being read as an official safety map. These tests build a small set of maps offline
and check that every place the text is generated still carries them.
"""

from __future__ import annotations

import datetime as dt
import json
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
    """Render it again with the same maps standing in for Tuesday as a second day."""
    facts, ctx = facts_ctx
    tuesday = {**facts, "day": "Tuesday, Nov. 24", "n_models": "two"}
    return fs.render(facts, ctx, [tuesday])


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
    assert site.blast_label("12:00") == "Monday, Nov. 23, 2026, 12:00 p.m. CST"
    assert site.blast_label("11:15") == "Monday, Nov. 23, 2026, 11:15 a.m. CST"


def test_pulled_label_for_the_legend() -> None:
    pulled = dt.datetime(2026, 11, 21, 12, 49, tzinfo=site.TZ)
    assert site.pulled_label(pulled) == "Nov. 21, 12:49 p.m. CST"
    morning = dt.datetime(2026, 11, 21, 8, 8, tzinfo=site.TZ)
    assert site.pulled_label(morning) == "Nov. 21, 8:08 a.m. CST"


def test_default_case_is_the_conservative_one() -> None:
    """Showing the EPA permit case first avoids a false sense of security."""
    assert site.DEFAULT_CASE == "permit"
    assert {c: r for c, r, _ in site.CASES}["permit"] == "permit-100"


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


def test_court_pause_note_in_about_dialog() -> None:
    """The About dialog reports the Eighth Circuit pause, with a link to the report."""
    page = site.PAGE_TEMPLATE.read_text(encoding="utf-8")
    start = page.index('<dialog id="note"')  # the "About this map" dialog
    about = page[start : page.index("</dialog>", start)]
    assert "<b>Court pause.</b> $court_pause" in about
    assert "$court_sources" in about
    assert f'href="{fs.COURT_URL}"' in fs.COURT_SOURCES_HTML
    assert f'href="{fs.FILING_URL}"' in fs.COURT_SOURCES_HTML
    assert fs.COURT_URL.startswith("https://www.iowapublicradio.org/")
    assert "until it rules on a request" in fs.COURT_PAUSE
    assert fs.COURT_PAUSE.endswith("These maps model Monday, Nov. 23.")


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
        "pct": {"low": "7%", "mid": "20%", "high": "55%", "permit": "100%"},
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


@pytest.mark.slow
def test_court_hold_leads_the_summary_and_faq(rendered: tuple[str, list, str]) -> None:
    """The court hold comes before any statement that the blast is Monday."""
    summary, faq, llms = rendered
    assert summary.index("Court hold") < summary.index("When will the detonation happen?")
    assert fs.COURT_URL in summary
    when = dict(faq)["When is the lead azide blast at the Iowa Army Ammunition Plant?"]
    assert when.startswith(
        "The Army now says Wednesday, Nov. 25, 2026; it hasn\u2019t given a time. It had "
        "planned Monday, Nov. 23, a court has put its permit on hold, and on Nov. 22 the "
        "government told the court the Army had postponed it to Tuesday, Nov. 24."
    )
    assert fs.WHY_WEDNESDAY in when
    assert fs.ARMY_WED_URL in when
    assert fs.COURT_PAUSE in when
    assert "on hold by court order" in llms
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
    """The summary, FAQ and llms.txt never point to the staged Tuesday/Wednesday maps."""
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
    """Monday's maps keep their old names; other days are prefixed with their date."""
    assert [d for d, _ in site.DAYS] == ["2026-11-23", "2026-11-24", "2026-11-25"]
    assert site.day_label("2026-11-25") == "Wednesday, Nov. 25"
    assert site.map_name("permit", "12:00") == "permit-1200.html"
    assert site.map_name("permit", "12:00", "2026-11-24") == "2026-11-24-permit-1200.html"
    assert site.map_key("2026-11-24", "low", "11:15") == "2026-11-24-low-1115"
    assert site.day_label("2026-11-24") == "Tuesday, Nov. 24"
    assert site.blast_label("12:00", "2026-11-24") == "Tuesday, Nov. 24, 2026, 12:00 p.m. CST"


def test_forecast_order_rrfs_then_gfs() -> None:
    """RRFS is shown where it covers the run (Monday); otherwise GFS (Tuesday)."""
    assert site.WEATHER.split(",")[:2] == ["ncep_rrfs_conus", "gfs_seamless"]


def test_days_to_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A deploy builds only the days its saved forecasts cover; a refresh builds them all."""
    cache = tmp_path / "map_met_all.json"
    monkeypatch.setattr(site, "MET_CACHE", cache)
    assert site.days_to_build() == ["2026-11-23", "2026-11-24", "2026-11-25"]  # downloading
    cache.write_text('{"x?start_date=2026-11-23&end_date=2026-11-24": 1}', encoding="utf-8")
    assert site.days_to_build() == ["2026-11-23"]
    cache.write_text(
        '{"a?start_date=2026-11-23&x": 1, "b?start_date=2026-11-24&x": 1}', encoding="utf-8"
    )
    assert site.days_to_build() == ["2026-11-23", "2026-11-24"]


def test_page_has_a_day_menu() -> None:
    page = site.PAGE_TEMPLATE.read_text(encoding="utf-8")
    assert '<select id="d">$day_options</select>' in page
    assert "$header_days" in page
    assert "MAP_FILES[day.value + '-' + cas.value + '-' + t]" in page


@pytest.mark.slow
def test_second_day_in_summary_faq_and_llms(rendered_two_days: tuple[str, list, str]) -> None:
    summary, faq, llms = rendered_two_days
    assert "<h3>If the blasts are on Tuesday, Nov. 24</h3>" in summary
    assert summary.index("If the blasts are on Tuesday") > summary.index("Lead in the air")
    assert "For noon Tuesday the forecast has surface winds" in summary
    assert "from two weather models" in summary  # its own model count
    assert summary.count(fs.TOWN_CAVEAT) >= 2  # the caveat after every list of towns
    answers = dict(faq)
    tue = answers["What if the blasts are on Tuesday, Nov. 24?"]
    assert fs.TOWN_CAVEAT in tue
    assert fs.CAVEAT in tue
    assert f"- Tuesday, Nov. 24 (also modeled): {fs.SAME_WINDOW}" in llms


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
    assert "at least 48 hours before the blasts and hourly from six hours before" in (
        fs.WHY_TUESDAY
    )
    # no longer "unclear" which day: the Nov. 22 filing says Tuesday
    assert "unclear" not in fs.COURT_HOLD
    assert "postponed the blasts to Tuesday, Nov. 24" in fs.COURT_HOLD
    assert fs.court_pause().endswith("These maps model Monday, Nov. 23.")
    assert fs.court_pause(["Tuesday, Nov. 24"]).endswith(
        "These maps model Monday, Nov. 23, and Tuesday, Nov. 24."
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
    both = "These maps model Monday, Nov. 23, and Tuesday, Nov. 24."
    assert both in summary
    assert both in dict(faq)["When is the lead azide blast at the Iowa Army Ammunition Plant?"]
    assert both in llms


def test_about_box_cites_the_tuesday_filing() -> None:
    """The About box's "When." paragraph gives Monday (Army) and Tuesday (KCCI), each sourced."""
    page = site.PAGE_TEMPLATE.read_text(encoding="utf-8")
    start = page.index('<dialog id="note"')
    about = " ".join(page[start : page.index("</dialog>", start)].split())
    assert "<b>When.</b> $why_monday Source:" in about
    assert "$why_tuesday Sources: $tuesday_sources." in about


@pytest.mark.slow
def test_summary_why_section_cites_both(rendered: tuple[str, list, str]) -> None:
    summary, faq, llms = rendered
    assert "<h3>When will the detonation happen?</h3>" in summary
    assert fs.WHY_TUESDAY in summary
    assert fs.TUESDAY_SOURCES_HTML in summary
    assert (
        fs.WHY_TUESDAY
        in dict(faq)["When is the lead azide blast at the Iowa Army Ammunition Plant?"]
    )
    assert f"- Why Tuesday: {fs.WHY_TUESDAY} Sources: {fs.TUESDAY_SOURCES_TEXT}" in llms


@pytest.mark.slow
def test_two_days_label_monday_and_keep_notes(rendered_two_days: tuple[str, list, str]) -> None:
    """With a second day, Monday's parts say Monday and each day keeps its notes."""
    summary, faq, llms = rendered_two_days
    for h in ("Where the cloud goes", "How far lead on the ground could reach", "Lead in the air"):
        assert f"<h3>{h} on Monday, Nov. 23</h3>" in summary
    # Monday's permit weather stays with the Army comparison, before the Tuesday section
    assert (
        summary.index("For noon Monday the forecast")
        < summary.index("If the blasts are on Tuesday")
        < summary.index("For noon Tuesday the forecast")
    )
    tue = summary[summary.index("If the blasts are on Tuesday") :]
    assert fs.REACH_NOTE in tue
    assert fs.SAME_WINDOW in tue
    assert "change before the blasts" in summary
    assert "before Monday" not in summary
    answers = dict(faq)
    assert answers["Where could the lead go?"].startswith("For Monday, Nov. 23: ")
    assert fs.REACH_NOTE in answers["What if the blasts are on Tuesday, Nov. 24?"]
    assert "- Monday, Nov. 23: Forecast pulled" in llms


def _fake_map(models: list[str]) -> str:
    return '{"airborneFraction": 0.07, "models":' + json.dumps(models) + "}"


def test_read_maps_days_and_model_counts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A day missing any blast time is left out; each day counts its own models."""
    monkeypatch.setattr(site, "MAPS", tmp_path)
    seven = [*site.WEATHER.split(","), "icon_seamless", "gem_seamless", "ukmo_seamless"]
    for c, _, _ in site.CASES:
        for t in site.TIMES:
            (tmp_path / site.map_name(c, t)).write_text(_fake_map(seven), encoding="utf-8")
            if t != "12:30":  # Tuesday is missing one time
                (tmp_path / site.map_name(c, t, "2026-11-24")).write_text(
                    _fake_map(seven[1:]), encoding="utf-8"
                )
    maps = site.read_maps()
    assert list(maps.days) == ["2026-11-23"]  # partly built Tuesday left out
    assert site.lead_day(maps) == site.DATE  # opens on Monday without Tuesday
    for c, _, _ in site.CASES:
        (tmp_path / site.map_name(c, "12:30", "2026-11-24")).write_text(
            _fake_map(seven[1:]), encoding="utf-8"
        )
    maps = site.read_maps()
    assert list(maps.days) == ["2026-11-23", "2026-11-24"]
    assert maps.days["2026-11-24"] == site.TIMES
    assert site.lead_day(maps) == "2026-11-24"  # Tuesday leads while Wednesday isn't built
    for c, _, _ in site.CASES:
        for t in site.TIMES:
            (tmp_path / site.map_name(c, t, "2026-11-25")).write_text(
                _fake_map(seven[:3]), encoding="utf-8"
            )
    maps = site.read_maps()
    assert list(maps.days) == ["2026-11-23", "2026-11-24", "2026-11-25"]
    assert site.lead_day(maps) == "2026-11-25" == site.LEAD_DAY  # then Wednesday
    assert site.model_count(maps.pages_by_day["2026-11-23"]) == "seven"
    assert site.model_count(maps.pages_by_day["2026-11-24"]) == "six"


def test_remove_days_not_built(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(site, "MAPS", tmp_path)
    (tmp_path / "permit-1200.html").write_text("mon", encoding="utf-8")
    (tmp_path / "2026-11-24-permit-1200.html").write_text("old tue", encoding="utf-8")
    site.remove_days_not_built(["2026-11-24", "2026-11-23"])
    assert (tmp_path / "2026-11-24-permit-1200.html").exists()
    site.remove_days_not_built(["2026-11-23"])
    assert not (tmp_path / "2026-11-24-permit-1200.html").exists()
    assert (tmp_path / "permit-1200.html").exists()  # the planned day is never removed


@pytest.fixture(scope="module")
def rendered_tuesday_lead(
    facts_ctx: tuple[dict[str, Any], dict[str, Any]],
) -> tuple[str, list, str]:
    """Render with Tuesday leading and Monday (the earlier planned date) after it."""
    facts, ctx = facts_ctx
    tuesday = {**facts, "day": "Tuesday, Nov. 24", "n_models": "one"}
    monday = {**facts, "day": fs.PLANNED_DAY, "n_models": "one"}
    return fs.render(tuesday, ctx, [monday])


@pytest.mark.slow
def test_tuesday_leads_and_monday_follows(rendered_tuesday_lead: tuple[str, list, str]) -> None:
    summary, faq, llms = rendered_tuesday_lead
    tue = "Tuesday, Nov. 24"
    note = fs.window_note(tue)
    assert note.startswith("No time has been given for Tuesday, so these maps use")
    assert fs.window_note(fs.PLANNED_DAY) == ""  # Monday has Iowa HHS's "about noon"
    assert summary.index(f"<h3>Where the cloud goes on {tue}</h3>") < summary.index(
        "<h3>Monday, Nov. 23, an earlier planned date</h3>"
    )
    lead = summary[summary.index("<h3>Where the cloud goes") :]
    assert lead.split("<p>", 1)[1].startswith(note)  # Tuesday's window is borrowed
    monday = summary[summary.index("an earlier planned date</h3>") :]
    assert "No time has been given" not in monday.split("</p>", 1)[0]
    days = "These maps model Monday, Nov. 23, and Tuesday, Nov. 24."
    assert days in summary
    qs = dict(faq)
    assert "What would the map show for Monday, Nov. 23, an earlier planned date?" in qs
    assert qs["Where could the lead go?"].startswith(f"For {tue}: ")
    assert "11 a.m. to 12:30 p.m. CST on Monday, Nov. 23, Tuesday, Nov. 24." in llms
    assert f"- {tue}: {note}" in llms
    assert "- Monday, Nov. 23 (also modeled): " in llms


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
    assert "<h3>Where the cloud goes on Monday, Nov. 23</h3>" in rendered_two_days[0]


def test_four_weather_models_and_hrrr_first_near_the_blast() -> None:
    """RRFS leads a day or more out; HRRR leads within 18 hours; four models in all."""
    assert site.WEATHER.split(",") == [
        "ncep_rrfs_conus",
        "gfs_seamless",
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
    days = [fs.PLANNED_DAY, "Tuesday, Nov. 24", "Wednesday, Nov. 25"]
    by = {d: {**facts, "day": d, "n_models": "one"} for d in days}
    return fs.render(by[days[2]], ctx, [by[days[0]], by[days[1]]])


@pytest.mark.slow
def test_wednesday_leads(rendered_wednesday_lead: tuple[str, list, str]) -> None:
    summary, faq, llms = rendered_wednesday_lead
    assert "<h3>Where the cloud goes on Wednesday, Nov. 25</h3>" in summary
    assert fs.window_note("Wednesday, Nov. 25") in summary
    for d in ("Monday, Nov. 23", "Tuesday, Nov. 24"):
        assert f"<h3>{d}, an earlier planned date</h3>" in summary
    assert summary.index("Wednesday, Nov. 25</h3>") < summary.index("Monday, Nov. 23, an")
    assert "These maps model Monday, Nov. 23, Tuesday, Nov. 24, and Wednesday, Nov. 25." in summary
    assert fs.WHY_WEDNESDAY in summary
    assert fs.WEDNESDAY_SOURCE_HTML in summary
    assert "Later that day, the Army said the blasts are now scheduled for Wednesday" in summary
    assert "- Why Wednesday: " in llms
    assert "on Monday, Nov. 23, Tuesday, Nov. 24, Wednesday, Nov. 25." in llms
    assert "What would the map show for Tuesday, Nov. 24, an earlier planned date?" in dict(faq)
