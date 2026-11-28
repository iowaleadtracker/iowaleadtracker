"""Write the site's pages, and the scripts and styles inside them, for the front-end linters.

The pages keep their JavaScript and CSS inline, and some are made by Python, so the linters
can't read them where they live. This writes, under OUT (default ``.lint``)::

    pages/<name>.html   each page, as the linters' HTML input
    js/<name>.<n>.js    each inline <script>
    css/<name>.<n>.css  each inline <style>

Each script and style is padded with blank lines so a reported line number is the line in
the page (for template.html, the line in the source file).
No model run is needed. The map template is read as it is; the 404, brief and staged pages
are rendered with sample data. The landing page is the built one when there is a build (CI
lints the build job's), else the template with stand-ins for its $placeholders.

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

import brief_page  # noqa: E402 - the scenario's modules, found through the path above
import make_map_picker as site  # noqa: E402
import site_style  # noqa: E402
import staged  # noqa: E402

BLOCK = re.compile(r"<(script|style)\b([^>]*)>(.*?)</\1>", re.DOTALL | re.IGNORECASE)
MARK = ".lint_pages"  # marks a folder this tool wrote, so a rerun may replace it
SAMPLE_TIME = "Wednesday, Nov. 25, 2026, 3:00 p.m. CST"


class _StandIns(dict[str, str]):
    """Fill every $placeholder: ``null`` inside a script, nothing elsewhere."""

    def __init__(self, *, in_script: bool) -> None:
        super().__init__(site_name=site.SITE_NAME, base_css=site_style.BASE_CSS)
        self.value = "null" if in_script else ""

    def __missing__(self, key: str) -> str:
        return self.value


def landing_page() -> tuple[str, str]:
    """Return the landing page to lint and where it came from.

    The built page (outputs/site/index.html) when there is one: it has the summary,
    questions and references, which are made from the built maps. Without a build, the
    template with its $placeholders filled by stand-ins.
    """
    built = site.SITE / "index.html"
    if built.exists():
        return built.read_text(encoding="utf-8"), str(built.relative_to(ROOT))
    text = site.PAGE_TEMPLATE.read_text(encoding="utf-8")
    out, pos = [], 0
    for m in BLOCK.finditer(text):
        out.append(Template(text[pos : m.start()]).safe_substitute(_StandIns(in_script=False)))
        out.append(
            Template(m.group(0)).safe_substitute(_StandIns(in_script=m.group(1) == "script"))
        )
        pos = m.end()
    out.append(Template(text[pos:]).safe_substitute(_StandIns(in_script=False)))
    return "".join(out), "index_template.html (no build: summary, questions, references left out)"


def pages() -> dict[str, str]:
    """Return {name: html} for every kind of page the site has."""
    days = dict.fromkeys(staged.DAYS, staged.TIMES)
    landing, source = landing_page()
    print(f"landing page: {source}")
    return {
        "map": (ROOT / "template.html").read_text(encoding="utf-8"),
        "landing": landing,
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
