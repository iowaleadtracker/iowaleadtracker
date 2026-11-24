"""Staged Wednesday to Friday maps: same model, other days, GFS and ECMWF only.

A set of maps at a hard-to-guess address on the main site, for people who have the link:
blasts on Wednesday, Nov. 25, Thursday, Nov. 26 and Friday, Nov. 27, 2026, every hour
from 9 a.m. to 1 p.m., for all four release cases, with only the GFS and ECMWF
forecasts (GFS shown, ECMWF in the weather-model spread).

These maps are not private. Nothing on the site links here, the pages are noindex, and the
folder is left out of the sitemap, robots.txt and llms.txt. The GitHub Pages mirror
carries it at the same address. This repository is public, so anyone reading it can find
the address.

The forecasts are saved in their own file (``met_cache/staged_forecasts.json``), so the
hourly refresh of the public maps never touches them. They are downloaded only by the
hand-started "Refresh staged forecast" workflow (``tools/refresh_forecast.py
--staged``), which proposes them as a pull request. Until that file exists, the build
makes no staged maps.

Run ``python staged.py --build`` to build only these maps (downloading the forecasts if
the file is missing), or let ``make_map_picker.py --build`` build them with the rest.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import shutil
import subprocess
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
#: The folder on the site. Hard to guess, but committed to a public repository.
DIR_NAME = "s-d8ac68fd00"
SITE = HERE / "outputs" / "site"
OUT = SITE / DIR_NAME
MAPS = OUT / "maps"
CACHE = HERE / "met_cache" / "staged_forecasts.json"
TZ = ZoneInfo("America/Chicago")
#: Wednesday (the Army's announced date, Nov. 22) through Friday.
DAYS = ["2026-11-25", "2026-11-26", "2026-11-27"]
TIMES = ["09:00", "10:00", "11:00", "12:00", "13:00"]  # forecast_summary.WINDOW
DEFAULT_DAY = DAYS[0]
DEFAULT_TIME = "12:00"
#: The first model is shown; the other makes up the weather-model spread.
WEATHER = "gfs_seamless,ecmwf_ifs025"
MODELS_TEXT = "GFS and ECMWF only (GFS shown; ECMWF in the weather-model spread)"

UNOFFICIAL = "This is an unofficial estimate, not from the Army or any government agency."
NOT_SAFE = "Don't use it to decide if you're safe."
#: When the blasts could happen: the government's Nov. 22 court filing ({url}), then the
#: Army's announcement later that day ({army}).
WHEN_HTML = (
    "The Army planned the detonation for Monday, Nov. 23. In a "
    '<a href="{url}">court filing on Nov. 22</a>, the government said the Army postponed it '
    'to Tuesday, Nov. 24; later that day, <a href="{army}">the Army said</a> it is now '
    "scheduled for Wednesday, Nov. 25. On Monday, Nov. 23, "
    '<a href="{trump}">President Trump said</a> he has ordered the military not to proceed '
    "until the Eighth Circuit agrees and Governor-elect Rob Sand agrees to the operation. "
    'Later that day, <a href="{ruling}">the 8th Circuit cleared the way</a> for the '
    'detonation. That evening, <a href="{secarmy}">the Acting Secretary of the Army said</a> '
    "the detonation will be Wednesday morning, as previously scheduled. The Army hasn&rsquo;t "
    "announced a time, and Thursday and Friday haven&rsquo;t been announced."
)


#: The picker page's styles (plain, so the page needs nothing from outside).
CSS = """
  :root { color-scheme: light dark; --bg: #fff; --ink: #1d1d1b; --muted: #555;
    --warn: #fde8c8; }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #1d1d1b; --ink: #f2f2f0; --muted: #b8b8b4; } }
  body { margin: 0; font: 15px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    background: var(--bg); color: var(--ink); }
  header { padding: 10px 16px; }
  h1 { font-size: 18px; margin: 0 0 6px; }
  .warn { background: var(--warn); color: #1d1d1b; padding: 8px 12px; border-radius: 6px;
    margin: 6px 0; }
  .about { color: var(--muted); font-size: 13.5px; margin: 6px 0; }
  .controls { display: flex; flex-wrap: wrap; gap: 8px 14px; align-items: center;
    margin: 8px 0 4px; }
  select, button { font: inherit; padding: 4px 8px; }
  iframe { display: block; width: 100%; border: 0; height: calc(100svh - 230px);
    min-height: 480px; }
"""


def map_name(day: str, case: str, t: str) -> str:
    """Return the file name of one map, e.g. ``2026-11-25-permit-1200.html``."""
    return f"{day}-{case}-{t.replace(':', '')}.html"


def day_label(day: str) -> str:
    """Return a day as 'Wednesday, Nov. 25, 2026'."""
    import make_map_picker as site  # noqa: PLC0415 - avoids a circular import

    d = dt.date.fromisoformat(day)
    month = site.AP_MONTHS.get(d.strftime("%B"), d.strftime("%B"))
    return f"{d.strftime('%A')}, {month} {d.day}, {d.year}"


def model_args() -> list[str]:
    """Return the public maps' model settings with this run's weather models and file."""
    import make_map_picker as site  # noqa: PLC0415

    args = list(site.MODEL_ARGS)
    args[args.index("--weather-model") + 1] = WEATHER
    args[args.index("--met-cache") + 1] = str(CACHE)
    return args


def build() -> None:
    """Run the model for every day, case and time (downloads only if CACHE is missing)."""
    import make_map_picker as site  # noqa: PLC0415

    MAPS.mkdir(parents=True, exist_ok=True)
    py = site.find_python()
    pulled = site.retrieved_at(CACHE) if CACHE.exists() else None
    as_of = ("--as-of", pulled.isoformat()) if pulled else ()
    sky = site.sky_grid_args()
    temperature = site.temperature_args(CACHE)  # before any download fills CACHE
    for day in DAYS:
        for case, release_case, name in site.CASES:
            for t in TIMES:
                # The forecast time is known only after the first download fills CACHE.
                pulled = site.retrieved_at(CACHE) if CACHE.exists() else None
                forecast = f", forecast from {site.pulled_label(pulled)}" if pulled else ""
                note = (
                    f"{name} case, blast {day_label(day)}, {site.label(t)} CST{forecast}, "
                    "GFS and ECMWF only"
                )
                cmd = [
                    py,
                    str(site.TOOL / "puff_dispersal.py"),
                    *("--lat", str(site.LAT)),
                    *("--lon", str(site.LON)),
                    *("--time", f"{day}T{t}-06:00"),
                    *("--release-case", release_case),
                    *model_args(),
                    *temperature,
                    *as_of,
                    *sky,
                    *("--home-url", site.SITE_URL),
                    *("--legend-note", note),
                    *("-o", str(MAPS / map_name(day, case, t))),
                ]
                print(f"building staged {day} {case} {t}", flush=True)
                # Arguments are built here from constants; no shell is involved.
                r = subprocess.run(  # noqa: S603
                    cmd, cwd=site.TOOL, capture_output=True, text=True, check=False
                )
                for line in r.stdout.splitlines() + r.stderr.splitlines():
                    if any(marker in line for marker in site.BUILD_LOG_MARKERS):
                        print("  " + line)
                if r.returncode:
                    raise SystemExit(
                        f"model run failed for staged {day} {case} {t}:\n{r.stderr[-2000:]}"
                    )
                if not as_of and CACHE.exists():  # replay the same pull for the rest
                    first = site.retrieved_at(CACHE)
                    as_of = ("--as-of", first.isoformat()) if first else ()


def complete_times(day: str) -> list[str]:
    """Return the blast times on ``day`` with a map for every case."""
    import make_map_picker as site  # noqa: PLC0415

    return [
        t for t in TIMES if all((MAPS / map_name(day, c, t)).exists() for c, _, _ in site.CASES)
    ]


def page_html(built_txt: str, got_txt: str, days: dict[str, list[str]]) -> str:
    """Return the picker page for the staged maps."""
    import forecast_summary as fs  # noqa: PLC0415
    import make_map_picker as site  # noqa: PLC0415

    files = {
        f"{day}-{c}-{t.replace(':', '')}": f"maps/{map_name(day, c, t)}"
        for day, times in days.items()
        for c, _, _ in site.CASES
        for t in times
    }
    day_opts = "".join(
        f'<option value="{d}"{" selected" if d == DEFAULT_DAY else ""}>{day_label(d)}</option>'
        for d in days
    )
    times = sorted({t for ts in days.values() for t in ts})
    time_opts = "".join(
        f'<option value="{t}"{" selected" if t == DEFAULT_TIME else ""}>{site.label(t)}</option>'
        for t in times
    )
    case_opts = "".join(
        f'<option value="{c}"{" selected" if c == site.DEFAULT_CASE else ""}>{n}</option>'
        for c, _, n in site.CASES
    )
    labels = [day_label(d) for d in days]
    day_list = labels[0] if len(labels) == 1 else "; ".join(labels[:-1]) + "; and " + labels[-1]
    when = WHEN_HTML.format(
        url=html.escape(fs.RESPONSE_URL),
        army=html.escape(fs.ARMY_WED_URL),
        trump=html.escape(fs.TRUMP_URL),
        ruling=html.escape(fs.RULING_URL),
        secarmy=html.escape(fs.SECARMY_URL),
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<meta name="referrer" content="no-referrer">
<title>{site.SITE_NAME}: Wednesday to Friday runs</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <h1>{site.SITE_NAME}: Wednesday to Friday runs</h1>
  <p class="warn" role="note"><b>{UNOFFICIAL} {NOT_SAFE}</b> Follow official instructions.</p>
  <p class="about">These maps model blasts on {day_list}, every hour from {fs.WINDOW}, with
    {MODELS_TEXT}. {when} Forecasts this far ahead change more and are less certain than
    the main site&rsquo;s. Weather forecast from {html.escape(got_txt)}. Last updated
    {html.escape(built_txt)}. Main site, summary and sources:
    <a href="{site.SITE_URL}">{site.SITE_URL.removeprefix("https://").rstrip("/")}</a>.</p>
  <div class="controls">
    <label>Day <select id="d">{day_opts}</select></label>
    <label>Blast time (CST) <select id="t">{time_opts}</select></label>
    <button id="prev" type="button">&lsaquo; Earlier</button>
    <button id="next" type="button">Later &rsaquo;</button>
    <label>Lead in the air <select id="c">{case_opts}</select></label>
  </div>
</header>
<iframe id="map" title="Map of where lead from the blast could travel and settle"></iframe>
<script>
const FILES = {json.dumps(files)};
const $ = (id) => document.getElementById(id);
function show() {{
  const key = $("d").value + "-" + $("c").value + "-" + $("t").value.replace(":", "");
  if (FILES[key]) $("map").src = FILES[key];
}}
function step(k) {{
  const s = $("t"); const i = s.selectedIndex + k;
  if (i >= 0 && i < s.options.length) {{ s.selectedIndex = i; show(); }}
}}
for (const id of ["d", "t", "c"]) $(id).onchange = show;
$("prev").onclick = () => step(-1);
$("next").onclick = () => step(1);
show();
</script>
</body>
</html>
"""  # noqa: S608 - HTML (its <select> menus), not SQL


def write_pages() -> int:
    """Write the picker page for the built maps; return the number of maps (0: none)."""
    import make_map_picker as site  # noqa: PLC0415

    days = {d: complete_times(d) for d in DAYS}
    days = {d: ts for d, ts in days.items() if ts}
    if not days:
        if OUT.exists():
            shutil.rmtree(OUT)
        return 0
    for mp in MAPS.glob("*.html"):  # maps opened on their own stay out of search results
        txt = mp.read_text(encoding="utf-8")
        if 'name="robots"' not in txt:
            mp.write_text(
                txt.replace("<head>", '<head>\n<meta name="robots" content="noindex">', 1),
                encoding="utf-8",
            )
    got = site.retrieved_at(CACHE)
    built_txt = site.fmt_time(dt.datetime.now(TZ))
    page = page_html(built_txt, site.fmt_time(got) if got else "unknown", days)
    (OUT / "index.html").write_text(page, encoding="utf-8")
    return sum(len(ts) for ts in days.values()) * len(site.CASES)


def links_to_staged(text: str) -> bool:
    """Say whether public text mentions the staged folder."""
    return re.search(re.escape(DIR_NAME), text) is not None


def main(argv: list[str] | None = None) -> None:
    """Build (optionally) and write the staged maps."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--build", action="store_true", help="run the model first")
    a = ap.parse_args(argv)
    if a.build:
        build()
    n = write_pages()
    print(f"wrote {n} staged maps to {OUT}" if n else "no staged maps built")


if __name__ == "__main__":
    main()
