"""The public page of the monitor-placement brief (scenarios/.../brief_page.py).

The page is built from the brief's README. These tests check that it keeps the site's
warnings, loads nothing from another site, shows all of the README, and is written into
the site and its mirror.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import struct
from typing import TYPE_CHECKING

import brief_page
import forecast_summary as fs
import make_map_picker as site
import mirror
import pytest
import staged

if TYPE_CHECKING:
    from pathlib import Path

BUILT = "November 26, 2026, at 7:00 a.m. CST"
SOF_MARKERS = {0xC0, 0xC1, 0xC2}


@pytest.fixture(scope="module")
def page() -> str:
    return brief_page.render(site.SITE_NAME, site.SITE_URL, BUILT)


def jpeg_size(path: Path) -> tuple[int, int]:
    """Return a JPEG's width and height, read from its start-of-frame segment."""
    data = path.read_bytes()
    i = 2
    while i < len(data):
        marker, length = data[i + 1], struct.unpack(">H", data[i + 2 : i + 4])[0]
        if marker in SOF_MARKERS:
            height, width = struct.unpack(">HH", data[i + 5 : i + 9])
            return width, height
        i += 2 + length
    raise ValueError("no frame header")


def test_page_carries_the_warnings(page: str) -> None:
    flat = " ".join(page.split())
    assert "This is an unofficial estimate, not from the Army or any government agency." in flat
    assert "Don't use it to decide if you're safe.</b> Follow official instructions." in flat
    # the brief's own notice, in the page's typography
    assert "Don\u2019t use it to decide if you\u2019re safe; follow official instructions." in flat
    assert "model estimates, not measurements" in flat.lower()
    assert flat.index("unofficial estimate") < flat.index("<h1>")  # the warning comes first
    # the header points to the agencies' own information
    header = flat.split("</header>")[0]
    assert "<b>Official information:</b>" in header
    assert f'href="{fs.EPA_VIEWER_URL}"' in header
    assert f'href="{fs.ARMY_MAPS_URL}"' in header
    assert not staged.links_to_staged(page)


def test_page_loads_nothing_from_another_site(page: str) -> None:
    """The content security policy allows only the site's own files and inline styles."""
    assert "<script" not in page
    assert "<iframe" not in page
    assert '<link rel="stylesheet"' not in page
    assert "@import" not in page
    assert "url(" not in page
    assert re.findall(r'<img[^>]* src="([^"]+)"', page) == [brief_page.MAP_FILE]
    assert "default-src 'none'" in site.CSP  # the policy this page has to live under
    assert "img-src 'self'" in site.CSP


def test_page_shows_all_of_the_readme(page: str) -> None:
    readme = brief_page.README.read_text(encoding="utf-8")
    tables = len(re.findall(r"^\|---", readme, flags=re.MULTILINE))
    assert tables >= 5
    assert page.count("<table>") == tables
    assert page.count("<h2 ") == len(re.findall(r"^## ", readme, flags=re.MULTILINE))
    faq = readme.split(f"## {brief_page.FAQ_HEADING}")[1].split("\n## ")[0]
    questions = re.findall(r"^\*\*(.+\?)\*\*$", faq, flags=re.MULTILINE)
    assert len(questions) > 10
    assert page.count("<h3 ") == len(questions)
    assert page.count("<figure>") == 1
    assert "<!--" not in page.split("<main")[1]  # the table markers stay out
    assert "**" not in page
    assert "](" not in page


def test_links_work_from_the_site(page: str) -> None:
    """Paths inside the repository go to GitHub; the rest are full addresses or on the site."""
    hrefs = re.findall(r'href="([^"]+)"', page)
    assert f"{brief_page.SOURCE_URL}/blob/main/{brief_page.REPO_FOLDER}/data/README.md" in hrefs
    assert brief_page.SOURCE_FOLDER_URL in hrefs
    assert "/" in hrefs  # back to the map; works on the main site and the mirror
    for href in hrefs:
        assert re.match(r"(https://|mailto:|/|#)", href) or href == brief_page.MAP_FILE, href
    assert f'<link rel="canonical" href="{site.SITE_URL}{brief_page.SLUG}/">' in page
    assert f"Last updated {BUILT}." in page


def test_markdown_the_page_cannot_show_stops_the_build() -> None:
    with pytest.raises(ValueError, match="heading level"):
        brief_page.to_html("# Title\n\n### Too deep\n")
    with pytest.raises(ValueError, match="can't show"):
        brief_page.to_html("A stray * asterisk.\n")


def test_text_is_escaped_and_typeset() -> None:
    _, body = brief_page.to_html('It\'s "5 < 6" & `a<b`, see https://example.org/x?a=1&b=2.\n')
    assert "It\u2019s \u201c5 &lt; 6\u201d &amp; <code>a&lt;b</code>" in body
    assert '<a href="https://example.org/x?a=1&amp;b=2" rel="noopener">' in body
    assert body.endswith("</a>.</p>")  # the sentence's period stays outside the link


def test_page_and_map_are_written_into_the_site(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(site, "SITE", tmp_path)
    now = dt.datetime(2026, 11, 26, 7, 0, tzinfo=site.TZ)
    site.write_site("<html></html>", "# llms\n", now)
    folder = tmp_path / brief_page.SLUG
    assert "<h1>" in (folder / "index.html").read_text(encoding="utf-8")
    assert jpeg_size(folder / brief_page.MAP_FILE) == brief_page.MAP_SIZE
    assert (folder / brief_page.MAP_FILE).stat().st_size < 1_000_000
    sitemap = (tmp_path / "sitemap.xml").read_text(encoding="utf-8")
    assert f"<loc>{site.SITE_URL}{brief_page.SLUG}/</loc>" in sitemap


def test_mirror_page_gets_the_policy(tmp_path: Path) -> None:
    built = tmp_path / "site"
    (built / "maps").mkdir(parents=True)
    (built / "m").mkdir()
    head = f'<head><link rel="canonical" href="{mirror.CANONICAL_URL}"></head>'
    (built / "index.html").write_text(f"<html>{head}<body></body></html>", encoding="utf-8")
    brief_page.write(built, site.SITE_NAME, site.SITE_URL, BUILT)
    out = tmp_path / "mirror"
    assert mirror.write_mirror(built, out, site.CSP) == 2
    text = (out / brief_page.SLUG / "index.html").read_text(encoding="utf-8")
    assert "Content-Security-Policy" in text
    assert (out / brief_page.SLUG / brief_page.MAP_FILE).exists()


def test_landing_page_header_has_the_official_links() -> None:
    """The landing page's official line and the analysis page's carry the same links."""
    template = site.PAGE_TEMPLATE.read_text(encoding="utf-8")
    assert '<p class="fema" role="note">$blast_status</p>' in template
    for link in (fs.EPA_VIEWER_URL, fs.ARMY_MAPS_URL):
        assert f'href="{link}"' in fs.BLAST_STATUS_HTML
    assert f'href="{fs.EPA_VIEWER_URL}"' in fs.OFFICIAL_HTML
    assert f'href="{fs.ARMY_MAPS_URL}"' in fs.OFFICIAL_HTML
    assert fs.ARMY_MAPS_URL == "https://www.army.mil/asc#org-iowa-army-ammunition-plant"
    assert "safe" not in fs.OFFICIAL_HTML.lower()


def test_landing_page_links_to_the_analysis() -> None:
    assert f'<a href="/{brief_page.SLUG}/">preliminary analysis</a>' in fs.EARLY_AIR_HTML
    assert brief_page.SLUG == "monitor-placement"  # the page's public address
    assert "safe" not in fs.EARLY_AIR_HTML.lower()  # still no verdicts about anyone's safety


def test_brief_says_what_ground_samples_can_show(page: str) -> None:
    """Corrected Nov. 26: wipes near the path can show the modeled lead; bulk soil can't."""
    readme = " ".join(brief_page.README.read_text(encoding="utf-8").split())
    assert "Corrected Nov. 26, 2026" in readme
    assert "Bulk soil samples probably can't." in readme
    assert "a sample taken afterward finds it" not in readme  # the claim that was too strong
    numbers = json.loads((brief_page.README.parent / "numbers.json").read_text(encoding="utf-8"))
    ground = numbers["ground"]
    assert ground["wipe_limit_ugft2"] == pytest.approx(4.0)  # 80% of EPA's 5 µg/ft² for floors
    for run in ground["runs"].values():
        # far less than the 22 mg/kg Iowa's soil holds, even if all of the lead got out
        assert run["soil_added_mgkg"] < 0.1
        assert run["soil_added_mgkg_all_airborne"] < 1.0 < ground["soil"]["lowest"]
        assert f"{run['highest_ugft2']:.0f} µg/ft²" in readme  # the table quotes the numbers
        assert f"out to {run['levels']['5']['miles_out']:.0f} mi" in readme
    assert "Table B." in page
    assert "soil sampling, can" not in fs.ANALYSIS
    assert "soil samples probably can\u2019t" in fs.ANALYSIS
