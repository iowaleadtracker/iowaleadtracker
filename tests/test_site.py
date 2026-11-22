"""The site's safety wording and settings can't silently disappear.

The warnings ("unofficial", "not from the Army", "don't use it to decide if you're
safe", the caveat after every town list) are the project's main protection against
being read as an official safety map. These tests build a small set of maps offline
and check that every place the text is generated still carries them.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import TYPE_CHECKING, Any

import forecast_summary as fs
import make_map_picker as site
import pytest
import unlisted
import works_cited

from dispersal.output import load_template, write_html

from .conftest import run_puff

if TYPE_CHECKING:
    from pathlib import Path

NOT_SAFE = "Don't use"
UNOFFICIAL = "unofficial estimate, not from the Army or any government agency"


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> tuple[str, list[tuple[str, str]], str]:
    """Summary HTML, FAQ and llms.txt for four noon maps under a steady north wind."""
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
    return fs.render(facts, ctx)


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
    assert f'href="{fs.EPA_FILING_URL}"' in fs.COURT_SOURCES_HTML
    assert fs.COURT_URL.startswith("https://www.iowapublicradio.org/")
    assert "until it rules on a request" in fs.COURT_PAUSE
    assert "in case they do" in fs.COURT_PAUSE


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
    assert summary.index("Court hold") < summary.index("Why the map is for Monday")
    assert fs.COURT_URL in summary
    when = dict(faq)["When is the lead azide blast at the Iowa Army Ammunition Plant?"]
    assert when.startswith(
        "The Army planned it for Monday, Nov. 23, 2026, but a court has put it on hold."
    )
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
def test_public_text_does_not_mention_unlisted_maps(rendered: tuple[str, list, str]) -> None:
    """The summary, FAQ and llms.txt never point to the unlisted Tuesday/Wednesday maps."""
    summary, faq, llms = rendered
    for text in (summary, llms, *(a for _, a in faq)):
        assert not unlisted.links_to_unlisted(text)
