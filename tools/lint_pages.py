"""Write the site's pages, and the scripts and styles inside them, for the front-end linters.

The pages keep their JavaScript and CSS inline, and some are made by Python, so the linters
can't read them where they live. This writes, under OUT (default ``.lint``)::

    pages/<name>.html   each page, as the linters' HTML input
    js/<name>.<n>.js    each inline <script>
    css/<name>.<n>.css  each inline <style>

Each script and style is padded with blank lines so a reported line number is the line in
the page (for template.html, the line in the source file).
No model run is needed: the map template is read as it is, and the landing page and the
Python pages are rendered from the saved forecasts with sample data (no map files).

Run with ``pnpm lint`` (package.json), or by hand: ``python3 tools/lint_pages.py [OUT]``.
"""

from __future__ import annotations

import datetime as dt
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCENARIO = ROOT / "scenarios" / "iowa-aap-lead-azide"
sys.path.insert(0, str(SCENARIO))
sys.path.insert(0, str(ROOT))

import brief_page  # noqa: E402 - the scenario's modules, found through the path above
import make_map_picker as site  # noqa: E402
import staged  # noqa: E402

BLOCK = re.compile(r"<(script|style)\b([^>]*)>(.*?)</\1>", re.DOTALL | re.IGNORECASE)
MARK = ".lint_pages"  # marks a folder this tool wrote, so a rerun may replace it
SAMPLE_NOW = dt.datetime(2026, 11, 27, 12, tzinfo=dt.timezone.utc)
SAMPLE_TIME = "Wednesday, Nov. 25, 2026, 3:00 p.m. CST"


def landing_page() -> str:
    """Return the landing page as the build writes it, with no map files.

    The summary, questions and references come from the saved forecasts' facts.
    """
    maps = site.Maps(
        pages=[],
        pct={c: "26%" for c, _, _ in site.CASES},
        times=site.TIMES,
        default=site.DEFAULT,
        days={site.DATE: site.TIMES},
        pages_by_day={site.DATE: []},
    )
    real = site.write_hashed_maps
    site.write_hashed_maps = lambda *_a, **_k: {}  # don't touch outputs/site/m
    try:
        return site.render_page(
            maps, dt.datetime(2026, 11, 27, tzinfo=dt.timezone.utc), SAMPLE_TIME
        )[0]
    finally:
        site.write_hashed_maps = real


def pages() -> dict[str, str]:
    """Return {name: html} for every kind of page the site has."""
    days = dict.fromkeys(staged.DAYS, staged.TIMES)
    return {
        "map": (ROOT / "template.html").read_text(encoding="utf-8"),
        "landing": landing_page(),
        "404": site.not_found_page(),
        "brief": brief_page.render(site.SITE_NAME, site.SITE_URL, SAMPLE_TIME),
        "staged": staged.page_html(SAMPLE_TIME, SAMPLE_TIME, days),
    }


def write(out: Path) -> int:
    """Write the pages and their inline code under ``out``; return the number of files."""
    if out.exists() and not (out / MARK).exists() and any(out.iterdir()):
        raise SystemExit(f"{out} isn't empty and wasn't written by this tool; not touching it")
    out.mkdir(parents=True, exist_ok=True)
    (out / MARK).write_text("written by tools/lint_pages.py\n", encoding="utf-8")
    for sub in ("pages", "js", "css"):  # only its own folders are replaced
        shutil.rmtree(out / sub, ignore_errors=True)
        (out / sub).mkdir()
    n = 0
    for name, page in pages().items():
        (out / "pages" / f"{name}.html").write_text(page, encoding="utf-8")
        n += 1
        for k, m in enumerate(BLOCK.finditer(page)):
            tag, attrs, body = m.group(1).lower(), m.group(2), m.group(3)
            if tag == "script" and re.search(r"type\s*=\s*[\"']?application/(ld\+)?json", attrs):
                continue  # data, not code
            pad = "\n" * page.count("\n", 0, m.start(3))
            ext = "js" if tag == "script" else "css"
            (out / ext / f"{name}.{k}.{ext}").write_text(pad + body, encoding="utf-8")
            n += 1
    return n


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / ".lint"
    print(f"wrote {write(target)} files to {target}")
