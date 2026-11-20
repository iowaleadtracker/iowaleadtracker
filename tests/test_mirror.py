"""The GitHub Pages mirror: notice, canonical link, security policy and file set."""

from __future__ import annotations

from typing import TYPE_CHECKING

import make_map_picker as site
import mirror
import pytest

if TYPE_CHECKING:
    from pathlib import Path

INDEX = (
    '<!doctype html><html><head><meta charset="utf-8">'
    f'<link rel="canonical" href="{mirror.CANONICAL_URL}"><title>t</title></head>'
    '<body class="x"><h1>Iowa Lead Tracker</h1></body></html>'
)
MAP = "<!doctype html>\n<html><head>\n<title>map</title></head><body>const DATA = 1;</body></html>"
LLMS = "# Iowa Lead Tracker\n\n> Summary.\n\nImportant: unofficial.\n"


def test_notice_names_the_main_site_and_why() -> None:
    out = mirror.mirror_index(INDEX, site.CSP)
    assert out.count(mirror.NOTICE_ID) == 1
    assert out.index("<body") < out.index(mirror.NOTICE_ID) < out.index("<h1>")
    assert f'href="{mirror.CANONICAL_URL}"' in mirror.NOTICE
    assert "networks that block Cloudflare" in mirror.NOTICE
    assert "GitHub Pages hosts it" in mirror.NOTICE


def test_canonical_link_stays_on_the_main_site() -> None:
    out = mirror.mirror_index(INDEX, site.CSP)
    assert f'<link rel="canonical" href="{mirror.CANONICAL_URL}">' in out
    with pytest.raises(ValueError, match="canonical"):
        mirror.mirror_index(INDEX.replace(mirror.CANONICAL_URL, mirror.MIRROR_URL), site.CSP)


def test_notice_is_added_once() -> None:
    with pytest.raises(ValueError, match="already"):
        mirror.mirror_index(mirror.mirror_index(INDEX, site.CSP), site.CSP)


def test_security_policy_moves_into_a_meta_tag() -> None:
    """GitHub Pages can't send headers; frame-ancestors is ignored in meta, so it's dropped."""
    tag = mirror.meta_csp(site.CSP)
    assert tag.startswith('<meta http-equiv="Content-Security-Policy"')
    assert "default-src 'none'" in tag
    assert "frame-ancestors" not in tag
    page = mirror.mirror_page(MAP, site.CSP)
    assert page.index("<head>") < page.index("Content-Security-Policy") < page.index("<title>")
    index = mirror.mirror_index(INDEX, site.CSP)
    assert index.index('<meta charset="utf-8">') < index.index("Content-Security-Policy")


def test_llms_note_comes_before_the_warning() -> None:
    out = mirror.mirror_llms(LLMS)
    assert out.index(mirror.CANONICAL_URL) < out.index("Important:")
    assert mirror.MIRROR_URL in out


def test_write_mirror(tmp_path: Path) -> None:
    built = tmp_path / "site"
    (built / "maps").mkdir(parents=True)
    (built / "m").mkdir()
    (built / "index.html").write_text(INDEX, encoding="utf-8")
    (built / "maps" / "low-1200.html").write_text(MAP, encoding="utf-8")
    (built / "m" / "low-1200-0123456789.html").write_text(MAP, encoding="utf-8")
    (built / "llms.txt").write_text(LLMS, encoding="utf-8")
    (built / "_headers").write_text("/*\n  X-Frame-Options: SAMEORIGIN\n", encoding="utf-8")
    (built / ".DS_Store").write_text("", encoding="utf-8")
    (built / "og.png").write_bytes(b"\x89PNG")
    out = tmp_path / "mirror"
    (out / "stale").mkdir(parents=True)  # replaced, not merged

    assert mirror.write_mirror(built, out, site.CSP) == 3
    assert not (out / "_headers").exists()
    assert not (out / ".DS_Store").exists()
    assert not (out / "stale").exists()
    assert (out / ".nojekyll").exists()
    assert (out / "og.png").read_bytes() == b"\x89PNG"
    assert mirror.NOTICE_ID in (out / "index.html").read_text(encoding="utf-8")
    for page in ("maps/low-1200.html", "m/low-1200-0123456789.html"):
        text = (out / page).read_text(encoding="utf-8")
        assert "Content-Security-Policy" in text
        assert mirror.NOTICE_ID not in text  # map pages carry their own banner
    # the source site is untouched
    assert mirror.NOTICE_ID not in (built / "index.html").read_text(encoding="utf-8")


def test_mirror_needs_a_built_site(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        mirror.write_mirror(tmp_path / "missing", tmp_path / "out", site.CSP)
