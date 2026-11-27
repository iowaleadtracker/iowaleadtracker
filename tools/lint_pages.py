"""Write the site's pages, and the scripts and styles inside them, for the front-end linters.

The pages keep their JavaScript and CSS inline, and some are made by Python, so the linters
can't read them where they live. This writes, under OUT (default ``.lint``)::

    pages/<name>.html   each page, as the linters' HTML input
    js/<name>.<n>.js    each inline <script>
    css/<name>.<n>.css  each inline <style>

Each script and style is padded with blank lines so a reported line number is the line in
the page: in template.html and index_template.html that is the line in the source file.
No model run is needed: the templates are read as they are (index_template.html's
``$placeholders`` filled with stand-ins) and the Python pages are rendered with sample data.

Run with ``pnpm lint`` (package.json), or by hand: ``python3 tools/lint_pages.py [OUT]``.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parent.parent
SCENARIO = ROOT / "scenarios" / "iowa-aap-lead-azide"
sys.path.insert(0, str(SCENARIO))
sys.path.insert(0, str(ROOT))

BLOCK = re.compile(r"<(script|style)\b([^>]*)>(.*?)</\1>", re.S | re.I)
SAMPLE_TIME = "Wednesday, Nov. 25, 2026, 3:00 p.m. CST"


class _StandIns(dict[str, str]):
    """Fill every $placeholder: ``null`` inside a script, nothing elsewhere."""

    def __init__(self, in_script: bool) -> None:
        super().__init__(site_name="Iowa Lead Tracker")
        self.value = "null" if in_script else ""

    def __missing__(self, key: str) -> str:
        return self.value


def fill_template(text: str) -> str:
    """Return index_template.html with its placeholders filled by stand-ins."""
    out, pos = [], 0
    for m in BLOCK.finditer(text):
        out.append(Template(text[pos : m.start()]).safe_substitute(_StandIns(False)))
        out.append(Template(m.group(0)).safe_substitute(_StandIns(m.group(1) == "script")))
        pos = m.end()
    out.append(Template(text[pos:]).safe_substitute(_StandIns(False)))
    return "".join(out)


def pages() -> dict[str, str]:
    """Return {name: html} for every kind of page the site has."""
    import brief_page
    import make_map_picker as site
    import staged

    days = {d: staged.TIMES for d in staged.DAYS}
    return {
        "map": (ROOT / "template.html").read_text(encoding="utf-8"),
        "landing": fill_template(site.PAGE_TEMPLATE.read_text(encoding="utf-8")),
        "404": site.not_found_page(),
        "brief": brief_page.render(site.SITE_NAME, site.SITE_URL, SAMPLE_TIME),
        "staged": staged.page_html(SAMPLE_TIME, SAMPLE_TIME, days),
    }


def write(out: Path) -> int:
    """Write the pages and their inline code under ``out``; return the number of files."""
    shutil.rmtree(out, ignore_errors=True)
    for sub in ("pages", "js", "css"):
        (out / sub).mkdir(parents=True)
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
