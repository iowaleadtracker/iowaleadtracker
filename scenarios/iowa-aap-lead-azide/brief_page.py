"""The public page of the monitor-placement brief, built from the brief's own README.

The brief (``postmortem/monitor-placement-brief/README.md``) is the one source of the
text: this module turns it into ``monitor-placement/index.html`` in the built site, in the
landing page's type and colors, so the page can't drift from the README. It reads a small,
fixed subset of Markdown, the subset that README uses: headings, paragraphs, bold, italic,
code, links, bare web addresses, lists, tables, one block quote, fenced code and images.
Anything else stops the build, so a README change that this module can't show is noticed.

The page follows the site's rules: it opens with the unofficial warning, loads nothing from
another site (the content security policy allows none), and links to the map.
"""

from __future__ import annotations

import html
import re
import shutil
from pathlib import Path
from string import Template

import site_style
from forecast_summary import OFFICIAL_HTML
from works_cited import (
    ANALYSIS_FOLDER,
    ANALYSIS_FOLDER_URL,
    ANALYSIS_PATH,
    CONTACT_EMAIL,
    SOURCE_URL,
)

HERE = Path(__file__).resolve().parent
BRIEF = HERE / "postmortem" / "monitor-placement-brief"
README = BRIEF / "README.md"
#: The page's folder in the site, and so its address.
SLUG = ANALYSIS_PATH.strip("/")
#: The map as the page shows it (a smaller copy of the README's PNG; brief.py writes both).
MAP_FILE = "monitor_placement_map.jpg"
MAP_SIZE = (1760, 1376)  # pixels, for the page to reserve the space
REPO_FOLDER = ANALYSIS_FOLDER
SOURCE_FOLDER_URL = ANALYSIS_FOLDER_URL
DESCRIPTION = (
    "A preliminary, unofficial analysis: EPA's four continuous lead monitors (AS01-AS04) for "
    "the Nov. 25, "
    "2026 detonation at the Iowa Army Ammunition Plant sat along the forecast path, and "
    "reruns on analyzed weather put the modeled cloud south of them. Model estimates, not "
    "measurements."
)
WARNING = (
    "<b>This is an unofficial estimate, not from the Army or any government agency. "
    "Don't use it to decide if you're safe.</b> Follow official instructions."
)
FAQ_HEADING = "Questions and answers"
_FENCE = "```"
_URL = re.compile(r"https?://[^\s<>]+")
_LIST = re.compile(r"^(-|\d+\.) +")
_STASH = "\x00{}\x00"

PAGE = Template("""<!doctype html><html lang="en-US"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>$title · $site_name</title>
<meta name="description" content="$description">
<meta name="robots" content="index, follow">
<link rel="canonical" href="$url">
<meta name="theme-color" content="#1f2933">
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta property="og:type" content="article">
<meta property="og:site_name" content="$site_name">
<meta property="og:title" content="$title">
<meta property="og:description" content="$description">
<meta property="og:url" content="$url">
<meta property="og:locale" content="en_US">
<meta property="og:image" content="$url$map_file">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="$title">
<meta name="twitter:description" content="$description">
<style>
$base_css
  header .site { margin: 0; font-size: 16px; font-weight: 700; }
  header .site a { color: inherit; text-decoration: none; }
  header .back { margin-left: auto; color: var(--sky); font-size: 13px; }
  header .official { margin: 0; flex-basis: 100%; color: var(--paper); font-size: 12.5px;
                     line-height: 1.4; }
  header .official b { color: #fff; }
  header .official a { color: var(--sky); }
  .doc h1 { font-size: 24px; line-height: 1.25; margin: 0 0 8px; }
  .doc h2 { font-size: 20px; margin: 28px 0 8px; }
  .doc ul, .doc ol { margin: 0 0 10px; padding-left: 1.4em; }
  .doc li { margin: 0 0 5px; }
  .doc .caveat { background: var(--peach); padding: 8px 12px; border-radius: 6px;
                 margin: 0 0 14px; }
  .doc .caveat p:last-child { margin-bottom: 0; }
  .doc .cap, .doc figcaption { color: var(--gray); font-size: 12.5px; }
  .doc code { font: 12.5px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
              background: var(--mist); padding: 1px 4px; border-radius: 3px;
              overflow-wrap: anywhere; }
  .doc pre { background: var(--mist); padding: 10px 12px; border-radius: 6px; overflow-x: auto; }
  .doc pre code { background: none; padding: 0; overflow-wrap: normal; }
  .doc figure { margin: 6px 0 14px; }
  .doc figure img { display: block; width: 100%; height: auto; border: 1px solid var(--silver);
                    border-radius: 6px; background: #fff; }
  .doc figcaption { margin-top: 6px; }
  .doc h2, .doc h3 { scroll-margin-top: 12px; }
  footer { max-width: 46rem; margin: 0 auto; padding: 0 16px 48px; color: var(--gray);
           font-size: 12.5px; line-height: 1.5; }
  footer a { color: var(--blue); }
  @media (max-width: 600px) {
    .doc h1 { font-size: 21px; }
  }
</style></head><body>
<header>
  <div class="title"><p class="site"><a href="/">$site_name</a></p>
    <p>Preliminary analysis</p></div>
  <a class="back" href="/">&lsaquo; Back to the map</a>
  <p class="warn" role="note">$warning</p>
  <p class="official" role="note">$official</p>
</header>
<main class="doc">
$body
</main>
<footer>
  <p>No warranty. Last updated $built_txt. The text, the code, and the data behind this page
    are public on <a href="$source_folder" rel="noopener">GitHub</a>, free to check, run, and
    improve. Questions or corrections:
    <a href="mailto:$contact">$contact</a>.</p>
  <p><a href="/">Go to the $site_name map</a></p>
</footer>
</body></html>
""")


def _slug(text: str) -> str:
    """Return a heading's anchor: lowercase words joined by hyphens."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _typeset(text: str) -> str:
    """Escape running text and give it the page's quotes and apostrophes."""
    text = html.escape(text, quote=False)
    text = re.sub(r"(?<=[\w.,?!%°)\x00])\"", "\u201d", text)  # closing double quote
    text = text.replace('"', "\u201c")  # the rest open
    return text.replace("'", "\u2019")


def _href(target: str) -> str:
    """Return a link target as the page needs it: repository paths go to GitHub."""
    if re.match(r"(https?:|mailto:|#|/)", target):
        return target
    kind = "tree" if target.endswith("/") else "blob"
    return f"{SOURCE_URL}/{kind}/main/{REPO_FOLDER}/{target}"


def inline(text: str) -> str:
    """Return one run of README text as HTML: code, links, bold, italic and addresses."""
    kept: list[str] = []

    def stash(markup: str) -> str:
        kept.append(markup)
        return _STASH.format(len(kept) - 1)

    def link(m: re.Match[str]) -> str:
        href = html.escape(_href(m.group(2)))
        rel = ' rel="noopener"' if href.startswith("http") else ""
        return stash(f'<a href="{href}"{rel}>{inline(m.group(1))}</a>')

    def bare(m: re.Match[str]) -> str:
        url = m.group(0).rstrip(".,;)")
        rest = m.group(0)[len(url) :]
        shown = html.escape(url)
        return stash(f'<a href="{shown}" rel="noopener">{shown}</a>') + rest

    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, text)
    text = re.sub(r"`([^`]+)`", lambda m: stash(f"<code>{html.escape(m.group(1))}</code>"), text)
    text = _URL.sub(bare, text)
    text = _typeset(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    if "*" in text or "](" in text:
        msg = f"brief page: Markdown this page can't show, in: {text[:80]!r}"
        raise ValueError(msg)
    return re.sub(r"\x00(\d+)\x00", lambda m: kept[int(m.group(1))], text)


def _table(rows: list[str]) -> str:
    """Return a Markdown table as HTML, in a wrapper that scrolls on phones."""
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    head, body = cells[0], cells[2:]
    out = [
        '<div class="tablewrap" tabindex="0" role="region" aria-label="Table"><table><thead><tr>'
    ]
    out += [f"<th>{inline(c)}</th>" for c in head]
    out.append("</tr></thead><tbody>")
    for row in body:
        out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in row) + "</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def _list(lines: list[str]) -> str:
    """Return a Markdown list as HTML. Continuation lines are indented in the README."""
    tag = "ol" if lines[0][0].isdigit() else "ul"
    items: list[str] = []
    for line in lines:
        if _LIST.match(line):
            items.append(_LIST.sub("", line))
        else:
            items[-1] += " " + line.strip()
    return f"<{tag}>" + "".join(f"<li>{inline(i)}</li>" for i in items) + f"</{tag}>"


def _blocks(text: str) -> list[list[str]]:
    """Split the README into blocks of lines: blank lines and code fences separate them."""
    blocks: list[list[str]] = []
    fenced = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith(_FENCE):
            if not fenced:
                blocks.append([line])
            fenced = not fenced
            if not fenced:
                blocks.append([])
            continue
        if fenced:
            blocks[-1].append(raw)
        elif not line or line.startswith("<!--"):
            blocks.append([])
        elif blocks and blocks[-1]:
            blocks[-1].append(line)
        else:
            blocks.append([line])
    return [b for b in blocks if b]


def _paragraph(lines: list[str], *, faq: bool) -> str:
    """Return a paragraph. In the questions section a bold first line is the question."""
    if faq and lines[0].startswith("**") and lines[0].endswith("**") and len(lines) > 1:
        question = lines[0].strip("*")
        answer = inline(" ".join(lines[1:]))
        return f'<h3 id="{_slug(question)}">{inline(question)}</h3><p>{answer}</p>'
    text = " ".join(lines)
    caption = text.startswith("*") and text.endswith("*") and not text.startswith("**")
    return f'<p class="cap">{inline(text.strip("*"))}</p>' if caption else f"<p>{inline(text)}</p>"


def _figure(image: re.Match[str], caption: list[str] | None) -> str:
    """Return the map as a figure, with the paragraph after it as its caption."""
    width, height = MAP_SIZE
    alt = html.escape(image.group(1))
    words = inline(" ".join(caption).strip("*")) if caption else ""
    return (
        f'<figure><a href="{MAP_FILE}"><img src="{MAP_FILE}" alt="{alt}" width="{width}" '
        f'height="{height}" decoding="async"></a>'
        f"<figcaption>{words} Select the map to open it full size.</figcaption></figure>"
    )


def _heading(line: str) -> tuple[int, str]:
    """Return a heading's level (1 or 2) and its words."""
    marks, _, words = line.partition(" ")
    if marks not in ("#", "##"):
        msg = f"brief page: heading level not handled: {line!r}"
        raise ValueError(msg)
    return len(marks), words


def to_html(text: str) -> tuple[str, str]:
    """Return the README's title and its body as HTML.

    Raises
    ------
    ValueError
        If the README uses Markdown this module doesn't show.
    """
    title = ""
    out: list[str] = []
    faq = False
    blocks = _blocks(text)
    skip = False
    for n, lines in enumerate(blocks):
        if skip:
            skip = False
            continue
        first = lines[0]
        image = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", " ".join(lines))
        if first.startswith(_FENCE):
            out.append(
                '<pre tabindex="0"><code>' + html.escape("\n".join(lines[1:])) + "</code></pre>"
            )
        elif first.startswith("#"):
            level, words = _heading(first)
            title = words if level == 1 else title
            faq = words == FAQ_HEADING
            anchor = "" if level == 1 else f' id="{_slug(words)}"'
            out.append(f"<h{level}{anchor}>{inline(words)}</h{level}>")
        elif first.startswith("|"):
            out.append(_table(lines))
        elif first.startswith(">"):
            inner = "\n".join(line[1:].lstrip() for line in lines)
            out.append(f'<div class="caveat" role="note">{to_html(inner)[1]}</div>')
        elif _LIST.match(first):
            out.append(_list(lines))
        elif image:
            after = blocks[n + 1] if n + 1 < len(blocks) else [""]
            skip = after[0].startswith("*") and not after[0].startswith("**")  # its caption
            out.append(_figure(image, after if skip else None))
        else:
            out.append(_paragraph(lines, faq=faq))
    return title, "\n".join(out)


def page_url(site_url: str) -> str:
    """Return the page's address on the site."""
    return f"{site_url}{SLUG}/"


def render(site_name: str, site_url: str, built_txt: str) -> str:
    """Return the page."""
    title, body = to_html(README.read_text(encoding="utf-8"))
    return PAGE.substitute(
        base_css=site_style.BASE_CSS,
        title=html.escape(title),
        site_name=site_name,
        description=html.escape(DESCRIPTION),
        url=page_url(site_url),
        map_file=MAP_FILE,
        warning=WARNING,
        official=OFFICIAL_HTML,
        body=body,
        built_txt=built_txt,
        source_folder=SOURCE_FOLDER_URL,
        contact=CONTACT_EMAIL,
    )


def write(site: Path, site_name: str, site_url: str, built_txt: str) -> Path:
    """Write the page and its map into the built site; return the page's path."""
    folder = site / SLUG
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(BRIEF / MAP_FILE, folder / MAP_FILE)
    dest = folder / "index.html"
    dest.write_text(render(site_name, site_url, built_txt), encoding="utf-8")
    return dest
