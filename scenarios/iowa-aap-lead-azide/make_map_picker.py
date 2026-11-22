#!/usr/bin/env python3
"""Build the iowaleadtracker.com site: one page with a blast-time and lead-in-the-air picker.

The site lives in outputs/site/: index.html plus one map per (case, time) in
outputs/site/maps/{case}-{HHMM}.html. The page loads only the map being looked at. The
page itself is index_template.html, filled in here.

    python3 make_map_picker.py --build    # run the model for every case and time
    python3 make_map_picker.py            # rewrite outputs/site/index.html from the maps
    python3 make_map_picker.py --publish  # also copy the site files to the publish folder
    python3 make_map_picker.py --deploy   # also upload the site to Cloudflare

--build needs the .venv. --deploy uploads to the Cloudflare Worker iowaleadtracker: it
runs `npx wrangler deploy` on a temporary folder whose public/ holds only the site, so
nothing else in the repo (or the wrangler config) is published. Log in once first with
`env -u CLOUDFLARE_API_TOKEN npx wrangler login`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from string import Template
from zoneinfo import ZoneInfo

import forecast_summary
import mirror
import staged
import works_cited

HERE = Path(__file__).resolve().parent
TOOL = HERE.parents[1]  # the repo root, where puff_dispersal.py lives
SITE = HERE / "outputs" / "site"
MAPS = SITE / "maps"
HASHED = SITE / "m"  # content-hashed copies of the maps, cached for a year
PAGE_TEMPLATE = HERE / "index_template.html"
MET_CACHE = HERE / "met_cache" / "map_met_all.json"
DATE = "2026-11-23"  # the planned blast day (CST, UTC-6); its maps keep their old names
# Days modeled, as (date, short code used in links). A day is built only when the saved
# forecasts include it (see build()), so adding one never makes a deploy download weather.
DAYS = [("2026-11-23", "mon"), ("2026-11-24", "tue")]
LAT, LON = 40.825518, -91.266502
TIMES = ["11:00", "11:15", "11:30", "11:45", "12:00", "12:15", "12:30"]
DEFAULT = "12:00"  # the Nov. 20 detonation had been set for about noon (Iowa HHS)
NOON_HOUR = 12
# (id used in file names and the URL, --release-case, label). See README "Release cases".
CASES = [
    ("low", "ap42-floor", "Low"),
    ("mid", "fine-20", "Middle"),
    ("high", "tnt-fine", "High"),
    ("permit", "permit-100", "EPA permit"),
]
DEFAULT_CASE = "permit"  # most conservative by default: better than a false sense of security
# The first model with data for the whole run is shown; the rest make up the spread. RRFS
# first (Monday), then GFS (Tuesday, until RRFS reaches that far), then the others.
WEATHER = (
    "ncep_rrfs_conus,gfs_seamless,ncep_hrrr_conus,ecmwf_ifs025,icon_seamless,"
    "gem_seamless,ukmo_seamless,meteofrance_seamless"
)
WEATHER_ORDER = WEATHER.split(",")
MODEL_ARGS = [
    *("--material", "lead-azide"),
    *("--explosive-mass", "9700lb"),
    *("--specific-energy", "1.64"),
    *("--shots", "2"),
    *("--confinement", "earth-covered"),
    *("--hours", "8"),
    *("--dt", "60"),
    *("--grid", "360"),
    *("--scale-min", "0.15ug"),
    *("--decades", "4"),
    *("--weather-model", WEATHER),
    *("--met-cache", str(MET_CACHE)),
]
# Lines of the model's output worth showing while building.
BUILD_LOG_MARKERS = ("skipped", "shown:", "Error", "Traceback")
CF_PROJECT = "iowaleadtracker"
# The GitHub Pages mirror (see mirror.py) is built and published by this workflow.
MIRROR_REPO = "iowaleadtracker/iowaleadtracker.github.io"
MIRROR_WORKFLOW = "mirror.yml"
WRANGLER = "wrangler@4.165.0"  # pinned; bump on purpose, not on every deploy
# The Cloudflare account that holds the domain. It is kept out of the repo: put
# {"cf_account_id": "..."} in deploy.local.json next to this script (git-ignored), or set
# IOWALEADTRACKER_CF_ACCOUNT_ID. Deploys always go to that account, even if the shell has
# other Cloudflare credentials; wrangler uses its own login, or the API token in
# IOWALEADTRACKER_CF_API_TOKEN (the GitHub Actions deploy, .github/workflows/deploy.yml).
LOCAL_CONFIG = HERE / "deploy.local.json"
CF_TOKEN_ENV = "IOWALEADTRACKER_CF_API_TOKEN"  # noqa: S105 - a variable name, not a secret
# A GitHub token allowed to start the mirror workflow; the Actions deploy sets it, since
# its own token can't start workflows in another repository. Locally, gh's login is used.
MIRROR_TOKEN_ENV = "IOWALEADTRACKER_MIRROR_TOKEN"  # noqa: S105 - a variable name
# Files besides maps/, m/ and brand/ that --publish copies.
PUBLISHED_FILES = (
    "index.html",
    "404.html",
    "robots.txt",
    "sitemap.xml",
    "og.png",
    "llms.txt",
    "_headers",
    "favicon.svg",
    "favicon.ico",
    "apple-touch-icon.png",
)

TZ = ZoneInfo("America/Chicago")
SITE_URL = "https://iowaleadtracker.com/"
SITE_NAME = "Iowa Lead Tracker"
DESCRIPTION = (
    "Unofficial, open-model map of where lead from the planned Nov. 23, 2026 blast at the "
    "Iowa Army Ammunition Plant could travel and settle, with its data, assumptions, and "
    "sources published."
)
# Response headers for Workers static assets (written to the site as _headers).
CSP = (
    "default-src 'none'; "
    "script-src 'self' 'unsafe-inline' https://static.cloudflareinsights.com; "
    "style-src 'unsafe-inline'; img-src 'self' data: blob: https://server.arcgisonline.com; "
    "connect-src 'self' https://cloudflareinsights.com; frame-src 'self'; "
    "frame-ancestors 'self'; "
    "base-uri 'none'; form-action 'none'; object-src 'none'; upgrade-insecure-requests"
)
PERMISSIONS = "camera=(), microphone=(), geolocation=(), payment=(), usb=(), browsing-topics=()"
HEADERS = f"""/*
  Content-Security-Policy: {CSP}
  X-Frame-Options: SAMEORIGIN
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: {PERMISSIONS}
  Cross-Origin-Opener-Policy: same-origin
  Strict-Transport-Security: max-age=31536000
/maps/*
  X-Robots-Tag: noindex
/m/*
  X-Robots-Tag: noindex
  Cache-Control: public, max-age=31536000, immutable
/llms.txt
  Content-Type: text/plain; charset=utf-8
/{staged.DIR_NAME}/*
  X-Robots-Tag: noindex, nofollow
  Referrer-Policy: no-referrer
"""
OG_IMAGE_META = (
    f'\n<meta property="og:image" content="{SITE_URL}og.png">'
    '\n<meta property="og:image:width" content="1200">'
    '\n<meta property="og:image:height" content="630">'
    '\n<meta property="og:image:alt" '
    'content="Map of the lead cloud\'s path from the Iowa Army Ammunition Plant">'
    f'\n<meta name="twitter:image" content="{SITE_URL}og.png">'
)
DEFAULT_WHO = "the Army, your county emergency management office, and state health officials"
# Official contacts for the disclaimer, as (name, url). Confirm each before adding it.
OFFICIAL_LINKS: list[tuple[str, str]] = []
NUMBER_WORDS = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
]
AP_MONTHS = {  # AP style abbreviates these months before a day
    "January": "Jan.",
    "February": "Feb.",
    "August": "Aug.",
    "September": "Sept.",
    "October": "Oct.",
    "November": "Nov.",
    "December": "Dec.",
}


# ---------------------------------------------------------------------------
# Local settings (kept out of the repo)


def local_setting(key: str, env: str, missing: str) -> str:
    """Return a maintainer setting from the environment or deploy.local.json.

    Parameters
    ----------
    key
        Key in deploy.local.json.
    env
        Environment variable that overrides the file.
    missing
        Message to exit with when neither has the setting.
    """
    if os.environ.get(env):
        return os.environ[env]
    try:
        with LOCAL_CONFIG.open(encoding="utf-8") as f:
            return str(json.load(f)[key])
    except (OSError, KeyError, ValueError) as err:
        raise SystemExit(missing) from err


def publish_dir() -> Path:
    """Return the folder --publish copies the site into (the maintainer's own)."""
    env = "IOWALEADTRACKER_PUBLISH_DIR"
    return Path(
        local_setting(
            "publish_dir",
            env,
            f'no publish folder: add "publish_dir" to {LOCAL_CONFIG} or set {env}',
        )
    )


def cf_account_id() -> str:
    """Return the Cloudflare account ID that --deploy uploads to."""
    return local_setting(
        "cf_account_id",
        "IOWALEADTRACKER_CF_ACCOUNT_ID",
        f"no Cloudflare account ID: create {LOCAL_CONFIG} with "
        '{"cf_account_id": "..."} or set IOWALEADTRACKER_CF_ACCOUNT_ID',
    )


# ---------------------------------------------------------------------------
# Names and times


def map_name(case: str, t: str, day: str = DATE) -> str:
    """Return a map's file name: 'permit-1200.html' (Monday), '2026-11-24-permit-1200.html'."""
    base = f"{case}-{t.replace(':', '')}.html"
    return base if day == DATE else f"{day}-{base}"


def map_key(day: str, case: str, t: str) -> str:
    """Return the page's key for a map: '2026-11-23-permit-1200'."""
    return f"{day}-{case}-{t.replace(':', '')}"


def day_label(day: str) -> str:
    """Return a day as 'Monday, Nov. 23'."""
    d = dt.date.fromisoformat(day)
    month = AP_MONTHS.get(d.strftime("%B"), d.strftime("%B"))
    return f"{d.strftime('%A')}, {month} {d.day}"


def cache_has_day(day: str, cache: Path | None = None) -> bool:
    """Say whether the saved forecasts (default: MET_CACHE) hold blasts on ``day``."""
    try:
        return f"start_date={day}" in (cache or MET_CACHE).read_text(encoding="utf-8")
    except OSError:
        return False


def label(t: str) -> str:
    """Return a 24-hour 'HH:MM' as '12:00 p.m.'."""
    h, m = map(int, t.split(":"))
    return f"{(h - 1) % 12 + 1}:{m:02d} {'a.m.' if h < NOON_HOUR else 'p.m.'}"


def fmt_time(t: dt.datetime) -> str:
    """Return a time as 'November 19, 2026, at 2:09 p.m. CST'."""
    return (
        t.strftime("%B %-d, %Y, at %-I:%M ")
        + ("a.m." if t.hour < NOON_HOUR else "p.m.")
        + " "
        + t.strftime("%Z")
    )


def blast_label(t: str, day: str = DATE) -> str:
    """Return a blast time on a day as 'Monday, Nov. 23, 2026, 12:00 p.m. CST'."""
    d = dt.datetime.fromisoformat(f"{day}T{t}").replace(tzinfo=TZ)
    month = AP_MONTHS.get(d.strftime("%B"), d.strftime("%B"))
    return f"{d.strftime('%A')}, {month} {d.day}, {d.year}, {label(t)} {d.strftime('%Z')}"


def pulled_label(d: dt.datetime) -> str:
    """Return a forecast download time as 'Nov. 21, 12:49 p.m. CST' for the map legend."""
    month = AP_MONTHS.get(d.strftime("%B"), d.strftime("%B"))
    return f"{month} {d.day}, {label(d.strftime('%H:%M'))} {d.strftime('%Z')}"


def retrieved_at(cache: Path = MET_CACHE) -> dt.datetime | None:
    """Return when the forecasts behind the maps (or another saved file) were downloaded.

    That is the oldest fetch stamp in the cache, or the cache file's write time for caches
    made before stamps were kept.
    """
    try:
        with cache.open(encoding="utf-8") as f:
            stamps = json.load(f).get("__fetched__") or {}
        if stamps:
            oldest = min(dt.datetime.fromisoformat(v) for v in stamps.values())
            return oldest.astimezone(TZ)
    except (OSError, ValueError):
        pass
    if cache.exists():
        files = [cache]
    elif cache != MET_CACHE:  # another file (the staged maps'): no stand-in
        return None
    else:  # older per-model caches, never the staged maps' own file
        files = [f for f in sorted(cache.parent.glob("*.json")) if f != staged.CACHE]
    if not files:
        return None
    return dt.datetime.fromtimestamp(min(f.stat().st_mtime for f in files), TZ)


def model_count(pages: list[str]) -> str:
    """Return the fewest weather models used by any of the maps, as a word ("seven")."""
    counts = []
    for page in pages:
        m = re.search(r'"models":\[([^\]]*)\]', page)
        if m:
            counts.append(len([x for x in m.group(1).split(",") if x.strip()]))
    n = min(counts) if counts else 0
    return NUMBER_WORDS[n] if n < len(NUMBER_WORDS) else str(n)


# ---------------------------------------------------------------------------
# Running the model


def find_python() -> str:
    """Return the Python of a .venv next to the model or above it, else this Python."""
    for d in (TOOL, *TOOL.parents):
        cand = d / ".venv" / "bin" / "python"
        if cand.exists():
            return str(cand)
    return sys.executable


def days_to_build() -> list[str]:
    """Return the days to build: all of them while downloading, else those saved.

    With no saved forecasts (a refresh), every day is built and downloaded. With saved
    forecasts (a deploy, which must not download), a day they don't cover is left out.
    """
    if not MET_CACHE.exists():
        return [d for d, _ in DAYS]
    days = [d for d, _ in DAYS if d == DATE or cache_has_day(d)]
    for d, _ in DAYS:
        if d not in days:
            print(f"no saved forecasts for {d} yet; leaving that day out")
    return days


def remove_days_not_built(days: list[str]) -> None:
    """Delete maps of extra days not being built: left over, they'd mix two forecasts."""
    for day, _ in DAYS:
        if day not in days and day != DATE:
            for old in MAPS.glob(f"{day}-*.html"):
                old.unlink()


def build() -> None:
    """Run the model for every day, case and time, one after another (Open-Meteo limits)."""
    MAPS.mkdir(parents=True, exist_ok=True)
    py = find_python()
    days = days_to_build()
    remove_days_not_built(days)
    # Replay the saved forecasts as of when they were pulled, so a rebuild on any later
    # date (or another machine) uses the same weather and makes the same maps.
    pulled = retrieved_at() if MET_CACHE.exists() else None
    as_of = ("--as-of", pulled.isoformat()) if pulled else ()
    forecast = f", forecast from {pulled_label(pulled)}" if pulled else ""
    for day in days:
        for case, release_case, name in CASES:
            for t in TIMES:
                cmd = [
                    py,
                    str(TOOL / "puff_dispersal.py"),
                    *("--lat", str(LAT)),
                    *("--lon", str(LON)),
                    *("--time", f"{day}T{t}-06:00"),
                    *("--release-case", release_case),
                    *MODEL_ARGS,
                    *as_of,
                    *("--home-url", SITE_URL),
                    *("--legend-note", f"{name} case, blast {blast_label(t, day)}{forecast}"),
                    *("-o", str(MAPS / map_name(case, t, day))),
                ]
                which = f"{case} {t}" if day == DATE else f"{day} {case} {t}"
                print(f"building {which}", flush=True)
                # Arguments are built here from constants; no shell is involved.
                r = subprocess.run(  # noqa: S603
                    cmd, cwd=TOOL, capture_output=True, text=True, check=False
                )
                for line in r.stdout.splitlines() + r.stderr.splitlines():
                    if any(marker in line for marker in BUILD_LOG_MARKERS):
                        print("  " + line)
                if r.returncode:
                    raise SystemExit(f"model run failed for {which}:\n{r.stderr[-2000:]}")
    if staged.CACHE.exists():  # the staged Tuesday/Wednesday maps, from their own file
        staged.build()


# ---------------------------------------------------------------------------
# The page


@dataclass
class Maps:
    """The built maps: page text, share of lead airborne per case, blast times present."""

    pages: list[str]
    pct: dict[str, str]
    times: list[str]  # the planned day's (DATE)
    default: str
    days: dict[str, list[str]] = field(default_factory=dict)  # every built day's times
    pages_by_day: dict[str, list[str]] = field(default_factory=dict)


def complete_times(day: str) -> list[str]:
    """Return the blast times on ``day`` with a map for every case."""
    return [t for t in TIMES if all((MAPS / map_name(c, t, day)).exists() for c, _, _ in CASES)]


def days_shown(times: list[str]) -> dict[str, list[str]]:
    """Return {day: blast times} for the planned day and every other day built in full.

    Another day is shown only with every one of the planned day's blast times, so the
    page's one time menu always has a map for the day chosen.
    """
    days = {DATE: times}
    for day, _ in DAYS:
        if day == DATE or not complete_times(day):
            continue
        if complete_times(day) == times:
            days[day] = times
        else:
            print(f"maps for {day} don't cover every blast time; leaving that day out")
    return days


def read_maps() -> Maps:
    """Read every complete blast time's maps and the share of lead airborne per case."""
    times = complete_times(DATE)
    if not times:
        raise SystemExit(f"no complete set of maps in {MAPS}; run with --build first")
    for t in TIMES:
        if t not in times:
            print(f"missing a map for {t}, leaving it out")
    days = days_shown(times)
    pages: list[str] = []
    pages_by_day: dict[str, list[str]] = {}
    share: dict[str, float] = {}
    for day, day_times in days.items():
        for case, _, _ in CASES:
            for t in day_times:
                page = (MAPS / map_name(case, t, day)).read_text(encoding="utf-8")
                pages.append(page)
                pages_by_day.setdefault(day, []).append(page)
                m = re.search(r'"airborneFraction":\s*([0-9.eE+-]+)', page)
                if m and case not in share:
                    share[case] = float(m.group(1))
    pct = {c: f"{share.get(c, 0) * 100:.0f}%" for c, _, _ in CASES}
    default = DEFAULT if DEFAULT in times else times[0]
    return Maps(
        pages=pages, pct=pct, times=times, default=default, days=days, pages_by_day=pages_by_day
    )


def models_used(pages: list[str]) -> list[str]:
    """Return the weather models any map used, in the preference order of WEATHER."""
    found: set[str] = set()
    for page in pages:
        m = re.search(r'"models":(\[[^\]]*\])', page)
        found.update(json.loads(m.group(1)) if m else [])
    return sorted(found, key=lambda m: WEATHER_ORDER.index(m) if m in WEATHER_ORDER else 99)


def json_ld(faq: list[tuple[str, str]], now: dt.datetime) -> str:
    """Return the page's schema.org structured data (WebPage and FAQPage)."""
    page = {
        "@type": "WebPage",
        "name": SITE_NAME,
        "url": SITE_URL,
        "description": DESCRIPTION,
        "inLanguage": "en-US",
        "isAccessibleForFree": True,
        "dateModified": now.isoformat(timespec="minutes"),
        "about": {
            "@type": "Place",
            "name": "Iowa Army Ammunition Plant",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": "Middletown",
                "addressRegion": "IA",
                "addressCountry": "US",
            },
            "geo": {"@type": "GeoCoordinates", "latitude": LAT, "longitude": LON},
        },
        "keywords": (
            "lead, lead azide, Iowa Army Ammunition Plant, Middletown, Burlington, "
            "Des Moines County, air quality, plume map, dust-lead"
        ),
        "citation": [forecast_summary.ARMY_URL, forecast_summary.PERMIT_URL],
        "abstract": forecast_summary.ABOUT_WHO,
        "creator": {"@type": "Person", "description": "A concerned Iowan (private citizen)"},
        "publisher": {
            "@type": "Organization",
            "name": SITE_NAME,
            "url": SITE_URL,
            "email": works_cited.CONTACT_EMAIL,
            "sameAs": [works_cited.INSTAGRAM_URL],
        },
        "isBasedOn": {
            "@type": "SoftwareSourceCode",
            "codeRepository": works_cited.SOURCE_URL,
            "programmingLanguage": "Python",
            "license": "https://opensource.org/licenses/MIT",
        },
    }
    faq_page = {
        "@type": "FAQPage",
        "url": SITE_URL + "#faq",
        "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in faq
        ],
    }
    data = {"@context": "https://schema.org", "@graph": [page, faq_page]}
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def write_hashed_maps(days: dict[str, list[str]]) -> dict[str, str]:
    """Copy each map to m/ under a content-hashed name; return {day-case-HHMM: path}.

    The plain maps/ files stay for old links. A map opened on its own points search
    engines at the home page.
    """
    shutil.rmtree(HASHED, ignore_errors=True)
    HASHED.mkdir(parents=True)
    map_files = {}
    for day, times in days.items():
        for case, _, _ in CASES:
            for t in times:
                mp = MAPS / map_name(case, t, day)
                txt = mp.read_text(encoding="utf-8")
                add = (
                    "" if 'name="robots"' in txt else '\n<meta name="robots" content="noindex">'
                ) + (
                    ""
                    if 'rel="canonical"' in txt
                    else f'\n<link rel="canonical" href="{SITE_URL}">'
                )
                if add:
                    txt = txt.replace("<head>", "<head>" + add, 1)
                    mp.write_text(txt, encoding="utf-8")
                stem = mp.name.removesuffix(".html")
                h = hashlib.sha256(txt.encode("utf-8")).hexdigest()[:10]
                shutil.copyfile(mp, HASHED / f"{stem}-{h}.html")
                map_files[map_key(day, case, t)] = f"m/{stem}-{h}"
    return map_files


_URL = re.compile(r"https?://[^\s<>\"]+?(?=[.,;:)]*(?:\s|$))")


def linkify(text: str) -> str:
    """Escape plain text for HTML and turn each web address in it into a link.

    Trailing sentence punctuation (".", ",", ")") stays outside the link.
    """
    escaped = html.escape(text)
    return _URL.sub(lambda m: f'<a href="{m.group(0)}" rel="noopener">{m.group(0)}</a>', escaped)


def faq_html(faq: list[tuple[str, str]]) -> str:
    """Return the visible FAQ: each question as a heading, its answer with live links."""
    return "".join(f"<h3>{html.escape(q)}</h3><p>{linkify(a)}</p>" for q, a in faq)


def render_page(maps: Maps, now: dt.datetime, built_txt: str) -> tuple[str, str]:
    """Return the landing page HTML and llms.txt for the built maps.

    Parameters
    ----------
    maps
        The built maps, from :func:`read_maps`.
    now
        Build time, for the structured data's dateModified.
    built_txt
        Build time as shown on the page ("Last updated ...").
    """
    pct, times = maps.pct, maps.times
    got = retrieved_at()
    got_txt = fmt_time(got) if got else "unknown"
    n_models = model_count(maps.pages_by_day.get(DATE, maps.pages))  # the planned day's
    f_facts = forecast_summary.facts(
        {(c, t): MAPS / map_name(c, t) for c, _, _ in CASES for t in times},
        CASES,
        times,
        maps.default,
    )
    # Other modeled days, described after the planned day in the summary, FAQ and llms.txt.
    more = []
    for day, day_times in maps.days.items():
        if day == DATE:
            continue
        default = maps.default if maps.default in day_times else day_times[0]
        f_day = forecast_summary.facts(
            {(c, t): MAPS / map_name(c, t, day) for c, _, _ in CASES for t in day_times},
            CASES,
            day_times,
            default,
        )
        f_day["day"] = day_label(day)
        f_day["n_models"] = model_count(maps.pages_by_day[day])
        more.append(f_day)
    summary_html, faq, llms_txt = forecast_summary.render(
        f_facts,
        {
            "pct": pct,
            "got_txt": got_txt,
            "n_models": n_models,
            "built_txt": built_txt,
            "site_name": SITE_NAME,
            "site_url": SITE_URL,
            "description": DESCRIPTION,
            "lat": LAT,
            "lon": LON,
        },
        more,
    )
    shown = f_facts["shown_model"]
    model_name = forecast_summary.MODEL_SHORT.get(shown, shown or "the first model")
    cite_models, cite_count = model_name, n_models
    if more:  # name each day's shown model and count in the References
        per_day = [(day_label(DATE).split(",")[0], model_name, n_models)] + [
            (
                m["day"].split(",")[0],
                forecast_summary.MODEL_SHORT.get(
                    m["shown_model"], m["shown_model"] or "the first model"
                ),
                m["n_models"],
            )
            for m in more
        ]
        cite_models = ", ".join(f"{model} ({wd})" for wd, model, _ in per_day)
        counts = {n for _, _, n in per_day}
        cite_count = (
            n_models if len(counts) == 1 else " and ".join(f"{n} ({wd})" for wd, _, n in per_day)
        )
    cite_html = works_cited.render(
        {
            "pct": pct,
            "n_models": cite_count,
            "got_txt": got_txt,
            "shown_model": cite_models,
            "models": models_used(maps.pages),
        },
        SITE_URL,
        built_txt,
    )
    og_image = OG_IMAGE_META if (SITE / "og.png").exists() else ""
    who = (
        ", ".join(
            f'<a href="{html.escape(u)}" target="_blank" rel="noopener">{html.escape(n)}</a>'
            for n, u in OFFICIAL_LINKS
        )
        or DEFAULT_WHO
    )
    values = {
        "site_name": SITE_NAME,
        "site_url": SITE_URL,
        "description": html.escape(DESCRIPTION),
        "og_image": og_image,
        "twitter_card": "summary_large_image" if og_image else "summary",
        "json_ld": json_ld(faq, now),
        "day_options": "".join(
            f'<option value="{d}"{" selected" if d == DATE else ""}>{day_label(d)}</option>'
            for d in maps.days
        ),
        "day_hidden": "" if len(maps.days) > 1 else " hidden",
        "day_codes": json.dumps({d: c for d, c in DAYS if d in maps.days}),
        "all_days": json.dumps({c: day_label(d) for d, c in DAYS}),
        "header_days": (
            day_label(DATE)
            if len(maps.days) == 1
            else f"{day_label(DATE)} (also modeled: "
            + ", ".join(day_label(d) for d in maps.days if d != DATE)
            + ")"
        ),
        "time_options": "".join(
            f'<option value="{t}"{" selected" if t == maps.default else ""}>{label(t)}</option>'
            for t in times
        ),
        "case_options": "".join(
            f'<option value="{c}"{" selected" if c == DEFAULT_CASE else ""}>'
            f"{name}: {pct[c]} of the lead</option>"
            for c, _, name in CASES
        ),
        "got_txt": got_txt,
        "n_models": n_models,
        "built_txt": built_txt,
        "built_json": json.dumps(built_txt),
        "pct_low": pct["low"],
        "pct_mid": pct["mid"],
        "pct_high": pct["high"],
        "pct_permit": pct["permit"],
        "about_who": forecast_summary.ABOUT_WHO,
        "source_url": works_cited.SOURCE_URL,
        "contact_html": works_cited.CONTACT_HTML,
        "misting": forecast_summary.MISTING,
        "advisory_url": forecast_summary.ADVISORY_URL,
        "court_pause": forecast_summary.court_pause([day_label(d) for d in maps.days if d != DATE]),
        "court_url": forecast_summary.COURT_URL,
        "court_cite": forecast_summary.COURT_CITE,
        "court_sources": forecast_summary.COURT_SOURCES_HTML,
        "time_head": forecast_summary.TIME_HEAD,
        "why_monday": forecast_summary.WHY_MONDAY,
        "why_tuesday": forecast_summary.WHY_TUESDAY,
        "filing_url": forecast_summary.EPA_FILING_URL,
        "filing_cite": forecast_summary.EPA_FILING_CITE,
        "army_url": forecast_summary.ARMY_URL,
        "army_cite": forecast_summary.ARMY_CITE,
        "time_note": forecast_summary.time_note(built_txt).replace(
            "(Iowa HHS fact sheet)", f"({forecast_summary.HHS_LINK})"
        ),
        "not_checked": forecast_summary.NOT_CHECKED,
        "who": who,
        "cite_html": cite_html,
        "summary_html": summary_html,
        "faq_html": faq_html(faq),
        "map_files": json.dumps(write_hashed_maps(maps.days), separators=(",", ":")),
    }
    template = Template(PAGE_TEMPLATE.read_text(encoding="utf-8").removesuffix("\n"))
    return template.substitute(values), llms_txt


def not_found_page() -> str:
    """Return the page served for any address that doesn't exist (404.html).

    Without it, Cloudflare answers a missing address with a bare 404 that has no content
    type, which iPhone Safari offers to download as a file.
    """
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Page not found · {SITE_NAME}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ margin: 0; padding: 32px 16px; font: 16px/1.5 system-ui, -apple-system, "Segoe UI",
    Roboto, sans-serif; background: #fff; color: #1d1d1b; }}
  @media (prefers-color-scheme: dark) {{ body {{ background: #1d1d1b; color: #f2f2f0; }}
    a {{ color: #8ab4f8; }} }}
  main {{ max-width: 560px; margin: 0 auto; }}
  h1 {{ font-size: 22px; margin: 0 0 8px; }}
  .warn {{ background: #fde8c8; color: #1d1d1b; padding: 10px 12px; border-radius: 6px; }}
</style>
</head>
<body>
<main>
  <h1>Page not found</h1>
  <p>There&rsquo;s no page at this address. It may have been mistyped, or not be
    published yet.</p>
  <p><a href="/">Go to the {SITE_NAME} map</a></p>
  <p class="warn"><b>This is an unofficial estimate, not from the Army or any government
    agency. Don&rsquo;t use it to decide if you&rsquo;re safe.</b> Follow official
    instructions.</p>
</main>
</body>
</html>
"""


def write_site(page: str, llms_txt: str, now: dt.datetime) -> Path:
    """Write index.html and the small site files; return the index path."""
    (SITE / "_headers").write_text(HEADERS, encoding="utf-8")
    (SITE / "404.html").write_text(not_found_page(), encoding="utf-8")
    (SITE / "llms.txt").write_text(llms_txt, encoding="utf-8")
    (SITE / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}sitemap.xml\n", encoding="utf-8"
    )
    (SITE / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{SITE_URL}</loc><lastmod>{now.date().isoformat()}</lastmod></url>\n"
        "</urlset>\n",
        encoding="utf-8",
    )
    dest = SITE / "index.html"
    dest.write_text(page, encoding="utf-8")
    return dest


# ---------------------------------------------------------------------------
# Publishing


def publish() -> None:
    """Copy the site into the maintainer's publish folder."""
    dest = publish_dir()
    for name in PUBLISHED_FILES:
        if (SITE / name).exists():
            shutil.copyfile(SITE / name, dest / name)
    for sub in ("maps", "m", "brand", staged.DIR_NAME):
        if (SITE / sub).is_dir():
            shutil.rmtree(dest / sub, ignore_errors=True)
            shutil.copytree(SITE / sub, dest / sub)
    print(f"copied index.html and maps/ to {dest}")


def wrangler_config(project: str) -> dict[str, object]:
    """Return the Worker settings for wrangler deploy."""
    return {
        "name": project,
        "compatibility_date": "2026-11-18",
        # A missing address gets 404.html (a real page), not a bare 404 that iPhone
        # Safari offers to download.
        "assets": {"directory": "./public", "not_found_handling": "404-page"},
        # Serve only on the custom domain: the workers.dev and preview
        # addresses contain the account's username.
        "workers_dev": False,
        "preview_urls": False,
    }


def deploy(project: str) -> None:
    """Upload the site to the Cloudflare Worker `project` with wrangler."""
    with tempfile.TemporaryDirectory() as d:
        # only site files: no dotfiles (.DS_Store), no caches
        shutil.copytree(
            SITE, Path(d) / "public", ignore=shutil.ignore_patterns(".*", "__pycache__", "*.pyc")
        )
        config = wrangler_config(project)
        (Path(d) / "wrangler.jsonc").write_text(json.dumps(config, indent=2), encoding="utf-8")
        cmd = ["npx", "--yes", WRANGLER, "deploy"]
        print("running:", " ".join(cmd), "in", d)
        env = wrangler_env(dict(os.environ), cf_account_id())
        # npx comes from PATH on purpose (the maintainer's Node install); fixed arguments.
        if subprocess.run(cmd, env=env, cwd=d, check=False).returncode:  # noqa: S603
            raise SystemExit(
                "deploy failed (log in first: env -u CLOUDFLARE_API_TOKEN npx wrangler login)"
            )


def wrangler_env(environ: dict[str, str], account_id: str) -> dict[str, str]:
    """Return the environment for wrangler: this project's account and credentials only.

    Every Cloudflare variable from the shell is dropped, so a token for some other
    account can't be used by accident. Wrangler then uses its own login, unless
    ``IOWALEADTRACKER_CF_API_TOKEN`` holds a token (as in the GitHub Actions deploy).
    """
    env = {k: v for k, v in environ.items() if not k.startswith(("CLOUDFLARE_", "CF_"))}
    env["CLOUDFLARE_ACCOUNT_ID"] = account_id
    env["WRANGLER_SEND_METRICS"] = "false"
    if environ.get(CF_TOKEN_ENV):
        env["CLOUDFLARE_API_TOKEN"] = environ[CF_TOKEN_ENV]
    return env


def _mirror_not_started(reason: str) -> None:
    """Say that the mirror build wasn't started, loudly when running in GitHub Actions.

    In Actions this is a warning annotation on the run and a line in its summary, so a
    green deploy doesn't hide a mirror that will lag until its own schedule notices.
    """
    msg = (
        f"could not start the mirror build ({reason}); it waits for its own "
        "15-minute check, which GitHub may delay or skip. Set MIRROR_DISPATCH_TOKEN "
        f"or run {MIRROR_WORKFLOW} in {MIRROR_REPO} by hand."
    )
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::warning title=Mirror not started::{msg}")
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with Path(summary).open("a", encoding="utf-8") as f:
                f.write(f"**Mirror not started:** {msg}\n")
    else:
        print(f"note: {msg}")


def trigger_mirror() -> None:
    """Start the GitHub Pages mirror build, if the GitHub CLI is available.

    The mirror builds from the pushed ``main`` branch, so push before deploying for
    both copies to match. Otherwise the mirror's own 15-minute check should notice, but
    GitHub runs scheduled workflows on a best-effort basis, so a failure to start it is
    reported (a warning in GitHub Actions).
    """
    gh = shutil.which("gh")
    if not gh:
        _mirror_not_started("gh not found")
        return
    env = dict(os.environ)
    if env.get(MIRROR_TOKEN_ENV):
        env["GH_TOKEN"] = env[MIRROR_TOKEN_ENV]
    # Arguments are constants and the gh path comes from PATH; no shell is involved.
    r = subprocess.run(  # noqa: S603
        [gh, "workflow", "run", MIRROR_WORKFLOW, "-R", MIRROR_REPO],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if r.returncode:
        _mirror_not_started(" ".join(r.stderr.split()) or f"gh exited {r.returncode}")
    else:
        print(f"started the GitHub Pages mirror build ({MIRROR_REPO}); it builds from main")


# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--build", action="store_true", help="run the model for every case and time first"
    )
    ap.add_argument(
        "--publish",
        action="store_true",
        help="also copy the site files to publish_dir from deploy.local.json",
    )
    ap.add_argument(
        "--deploy",
        action="store_true",
        help=f"also upload the site to the Cloudflare Worker '{CF_PROJECT}'",
    )
    ap.add_argument("--project", default=CF_PROJECT, help="Cloudflare Worker name for --deploy")
    ap.add_argument(
        "--mirror",
        metavar="DIR",
        help="also write the GitHub Pages mirror of the site to DIR (see mirror.py)",
    )
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Build (optionally), write, publish and deploy the site."""
    a = parse_args(argv)
    if a.build:
        build()
    maps = read_maps()
    built_txt = fmt_time(dt.datetime.now(TZ))
    now = dt.datetime.now(TZ)
    page, llms_txt = render_page(maps, now, built_txt)
    dest = write_site(page, llms_txt, now)
    n_staged = staged.write_pages()
    if n_staged:
        print(f"wrote {n_staged} staged maps to {staged.OUT}")
    print(
        f"wrote {dest} ({len(maps.times)} times x {len(CASES)} cases; lead in the air: "
        + ", ".join(f"{n} {maps.pct[c]}" for c, _, n in CASES)
        + ")"
    )
    if a.mirror:
        n = mirror.write_mirror(SITE, Path(a.mirror), CSP)
        print(f"wrote the mirror to {a.mirror} ({n} pages)")
    if a.publish:
        publish()
    if a.deploy:
        deploy(a.project)
        trigger_mirror()


if __name__ == "__main__":
    main()
