"""The GitHub Pages mirror of the site, for readers who can't reach iowaleadtracker.com.

Some networks block Cloudflare or the domain itself, so the same
build is also published at https://iowaleadtracker.github.io/. This module turns the built
site (``outputs/site``) into that copy:

- a notice at the top of the page names the main site and says why the copy exists;
- ``rel=canonical`` keeps pointing at iowaleadtracker.com, so search engines treat this
  as a copy;
- the content security policy goes into a ``<meta>`` tag, because GitHub Pages can't
  send the response headers that ``_headers`` gives Cloudflare;
- ``.nojekyll`` tells GitHub Pages to serve the files as they are.

It is called by ``make_map_picker.py --mirror DIR`` and by the GitHub Action in the
iowaleadtracker/iowaleadtracker.github.io repository.
"""

from __future__ import annotations

import re
import shutil
from typing import TYPE_CHECKING

from staged import DIR_NAME as STAGED_DIR
from works_cited import SOURCE_URL

if TYPE_CHECKING:
    from pathlib import Path

CANONICAL_URL = "https://iowaleadtracker.com/"
MIRROR_URL = "https://iowaleadtracker.github.io/"
NOTICE_ID = "mirror-notice"

NOTICE = (
    f'<div id="{NOTICE_ID}" role="note" style="background:#fdf0d5;color:#1d1d1b;'
    "padding:8px 14px;font:14px/1.45 system-ui,-apple-system,sans-serif;text-align:center;"
    'border-bottom:1px solid #e3d3a8">'
    f'<b>This is a mirror.</b> The main site is <a href="{CANONICAL_URL}">iowaleadtracker.com</a>. '
    "This copy, built from the same "
    f'<a href="{SOURCE_URL}" rel="noopener">source code</a>, is for people who can&rsquo;t '
    "reach that address, for example on networks that block Cloudflare. GitHub Pages "
    "hosts it and sees visitors&rsquo; IP addresses; it "
    "doesn&rsquo;t count visits.</div>"
)
LLMS_NOTE = (
    f"> Mirror: the canonical site is {CANONICAL_URL}. This copy at {MIRROR_URL} is built "
    "from the same source for readers who can't reach that domain (for example on "
    "networks that block Cloudflare).\n"
)


def meta_csp(csp: str) -> str:
    """Return the policy as a ``<meta>`` tag, without directives a meta tag can't carry.

    Browsers ignore ``frame-ancestors`` (and ``report-uri``/``sandbox``) in a meta
    policy and warn about it, so those are dropped.
    """
    unsupported = ("frame-ancestors", "report-uri", "report-to", "sandbox")
    kept = [
        d.strip() for d in csp.split(";") if d.strip() and not d.strip().startswith(unsupported)
    ]
    return f'<meta http-equiv="Content-Security-Policy" content="{"; ".join(kept)}">'


def _after_head(html: str, tag: str) -> str:
    """Insert ``tag`` right after the opening ``<head>`` (after a charset meta if first)."""
    m = re.search(r"<head[^>]*>(\s*<meta charset=[^>]*>)?", html, re.IGNORECASE)
    if not m:
        raise ValueError("page has no <head>")
    return html[: m.end()] + tag + html[m.end() :]


def mirror_page(html: str, csp: str) -> str:
    """Return a map page with the security policy as a meta tag."""
    return _after_head(html, meta_csp(csp))


def mirror_index(html: str, csp: str) -> str:
    """Return the landing page with the mirror notice and the meta security policy.

    The canonical link is left pointing at the main site.
    """
    if NOTICE_ID in html:
        raise ValueError("page already has a mirror notice")
    if f'<link rel="canonical" href="{CANONICAL_URL}">' not in html:
        raise ValueError("landing page must keep its canonical link to the main site")
    html = mirror_page(html, csp)
    m = re.search(r"<body[^>]*>", html, re.IGNORECASE)
    if not m:
        raise ValueError("page has no <body>")
    return html[: m.end()] + NOTICE + html[m.end() :]


def mirror_llms(text: str) -> str:
    """Return llms.txt with the mirror note after its title and summary."""
    marker = "\n\nImportant:"
    if marker not in text:
        raise ValueError("llms.txt has no 'Important:' line to place the note before")
    return text.replace(marker, "\n\n" + LLMS_NOTE.rstrip("\n") + marker, 1)


def write_mirror(site: Path, out: Path, csp: str) -> int:
    """Copy the built site to ``out`` as the GitHub Pages mirror; return pages changed.

    ``out`` is replaced. Cloudflare's ``_headers`` is left out (GitHub Pages ignores
    it); the policy is carried in each page instead.
    """
    if not (site / "index.html").exists():
        raise SystemExit(f"no built site in {site}; run make_map_picker.py first")
    if out.exists():
        shutil.rmtree(out)
    # The staged maps stay on the main site only (see staged.py).
    shutil.copytree(site, out, ignore=shutil.ignore_patterns("_headers", ".*", STAGED_DIR))
    index = out / "index.html"
    index.write_text(mirror_index(index.read_text(encoding="utf-8"), csp), encoding="utf-8")
    pages = 1
    not_found = out / "404.html"  # GitHub Pages serves it for missing addresses too
    if not_found.exists():
        not_found.write_text(
            mirror_page(not_found.read_text(encoding="utf-8"), csp), encoding="utf-8"
        )
    for page in sorted([*(out / "maps").glob("*.html"), *(out / "m").glob("*.html")]):
        page.write_text(mirror_page(page.read_text(encoding="utf-8"), csp), encoding="utf-8")
        pages += 1
    llms = out / "llms.txt"
    if llms.exists():
        llms.write_text(mirror_llms(llms.read_text(encoding="utf-8")), encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    return pages
