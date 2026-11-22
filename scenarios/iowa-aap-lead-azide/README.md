# Iowa AAP lead azide scenario, Mon Nov 23, 2026 (first planned for Fri Nov 20)

Everything needed to rerun the maps for the planned
detonation at Iowa Army Ammunition Plant (40.825518° N, 91.266502° W).

**Why Monday:** on Nov. 19, 2026, the Army postponed the detonation from Friday, Nov. 20, to
Monday, Nov. 23, "until the latest possible moment prior to a forecasted temperature drop,"
which "would risk further destabilization of the material." Source: Army Sustainment Command,
"Postponed: Lead Azide Detonation," https://www.army.mil/article/296926. The article gives no
time, so the maps cover 11 a.m. to 12:30 p.m.

Inputs: about 9,700 lb of lead azide in 68 drums (Army Sustainment Command spokesperson via
ABC News, 19 Nov 2026; 68 drums per EPA's emergency permit, which redacts the weight), two
blasts around noon inside earth-covered magazines (Iowa HHS fact sheet; EPA permit), cloud
height halved, and 7%, 20%, 55% or 100% of the lead airborne in breathable sizes. The 100% case
matches the emission factor of 1.00 EPA's permit requires for the Army's own plume maps (see [Release cases](#release-cases-research-notes)). This is a screening model,
not official guidance.

## What is here

| File | What it is |
|---|---|
| `make_map_picker.py` | builds the iowaleadtracker.com site: every map, the picker page, publish and deploy |
| `mirror.py` | turns the built site into the GitHub Pages mirror |
| `index_template.html` | the landing page's HTML, CSS and script, filled in by `make_map_picker.py` |
| `met_cache/map_met_all.json` | saved Open-Meteo forecasts for Monday at the new site (download times in `__fetched__`; the page shows when) |
| `make_icons.py` | builds the site icons and profile images |
| `outputs/site/` | the site. The repo holds only the hand-made files (`og.png`, icons, `brand/`); `make_map_picker.py --build` writes the page and the maps |

## Set up

```bash
pip install -r requirements.txt     # from the repo root
```

## Rerun the map

From the repo root:

```bash
python3 puff_dispersal.py --lat 40.825518 --lon -91.266502 \
    --time 2026-11-23T12:00-06:00 \
    --material lead-azide --explosive-mass 9700lb --specific-energy 1.64 \
    --shots 2 --confinement earth-covered --release-case fine-20 \
    --hours 8 --dt 60 --grid 360 --scale-min 0.15ug --decades 4 \
    --met-cache scenarios/iowa-aap-lead-azide/met_cache/map_met_all.json \
    -o scenarios/iowa-aap-lead-azide/outputs/map_noon.html
```

Useful changes:

- **Start time:** `--time 2026-11-23T11:30-06:00`.
- **How much lead is airborne:** `--release-case ap42-floor` (7%), `fine-20` (20%),
  `tnt-fine` (55%) or `permit-100` (100%, the EPA permit's emission factor). See [Release cases](#release-cases-research-notes).
- **Explosive mass:** `--explosive-mass 5ton` is U.S. tons; `5t` is metric tons.
- **Weather models:** the default runs ECMWF, GFS, ICON, GEM, UKMO and Météo-France,
  plus HRRR when it covers the run, and shows the first. `--weather-model
  ncep_hrrr_conus,ecmwf_ifs025` puts HRRR first; `--weather-model best-match` uses one
  forecast.
- **Wind-direction spread:** add `--ensemble 5 --dir-spread 10`.
- **Near the site:** add `--extent-km 15 --hours 2`.

The site's maps use `--weather-model
ncep_rrfs_conus,gfs_seamless,ncep_hrrr_conus,ecmwf_ifs025,icon_seamless,gem_seamless,ukmo_seamless,meteofrance_seamless`:
RRFS is shown when it covers the run (Monday), then GFS (Tuesday, until RRFS reaches it), then
HRRR. Models with no data yet are skipped. (HRRR used to be first; RRFS is shown for Monday
on purpose, Nov. 22, 2026.)

In the page, "Levels of concern" with the "weather-model spread" box ticked shows
everywhere any model puts lead.

## The site (iowaleadtracker.com)

The home page has a blast-time dropdown (11:00 a.m. to 12:30 p.m., every 15 minutes), a
"Lead in the air" dropdown (Low, Middle, High, EPA permit), and a U.S./metric switch. It loads
one map at a time, so the first visit stays small. The settings for the model runs (place,
date, mass, weather models) are at the top of `make_map_picker.py`.

```bash
python3 make_map_picker.py --build --publish --deploy
```

- `--build` runs the model for all 28 maps, one after another (about 3 minutes once the
  forecasts are cached). With `met_cache/map_met_all.json` present, each run gets
  `--as-of` set to when those forecasts were pulled, so a rebuild on any later date or
  machine replays the same weather offline and makes the same maps.
- `--publish` copies the site files to the folder named by `publish_dir` in
  `deploy.local.json` (or `IOWALEADTRACKER_PUBLISH_DIR`). Only the maintainer needs it.
- `--deploy` uploads `outputs/site/` to the Cloudflare Worker on the account that owns the
  domain, with the workers.dev and preview addresses turned off. It needs
  `deploy.local.json` next to the script (git-ignored), holding
  `{"cf_account_id": "..."}`, or `IOWALEADTRACKER_CF_ACCOUNT_ID` set. Wrangler is pinned
  (`WRANGLER` in the script), every `CLOUDFLARE_*`/`CF_*` variable is dropped from the
  environment so wrangler uses its own login (or the token in
  `IOWALEADTRACKER_CF_API_TOKEN`), and dotfiles are never uploaded. It then starts the
  GitHub Pages mirror build (below) with `gh`, if installed.

**Deploying from GitHub.** `.github/workflows/deploy.yml` does the same on every merge to
`main` that touches the model or the site, and on demand: full tests, an offline build
from the saved forecasts, `--deploy`, then a check that the live page shows that build.
It skips the tests and the build (about 20 minutes) when CI already built and tested the
same files: CI saves its site as `site-<key>` (`tools/site_key.py` hashes everything the
build reads), and the deploy downloads it after checking the CI run passed and its commit
has the same key. `--deploy` still rewrites the landing page, so "Last updated" is the
deploy time. Merging a pull request that isn't up to date with `main`, or before its CI
finishes, falls back to building.
Its secrets live in the `cloudflare` environment, which only `main` can use:
`CLOUDFLARE_API_TOKEN` (the "Edit Cloudflare Workers" token template),
`CLOUDFLARE_ACCOUNT_ID`, and optionally `MIRROR_DISPATCH_TOKEN` (a fine-grained GitHub token
with Actions read and write on the mirror repository) to start the mirror at once.
- `--mirror DIR` writes the GitHub Pages copy of the site to `DIR` (see `mirror.py`).

**The mirror.** https://iowaleadtracker.github.io/ serves the same site for readers who
can't reach iowaleadtracker.com, for example on networks that block Cloudflare. The
workflow in
[iowaleadtracker/iowaleadtracker.github.io](https://github.com/iowaleadtracker/iowaleadtracker.github.io)
checks out this repository's `main`, runs `make_map_picker.py --build --mirror`, and
publishes the result: on demand, when `--deploy` starts it, and within 15 minutes whenever
`main` has a new commit. It builds from `main`, so a merge updates the public mirror
even without a deploy. The mirror adds a notice naming the
main site, keeps `rel=canonical` on iowaleadtracker.com, carries the security policy in a
`<meta>` tag (GitHub Pages can't send `_headers`), and fails without publishing if the build
would have to download weather the saved forecasts don't have.

What `outputs/site/` holds:

| Path | What it is |
|---|---|
| `index.html` | the page |
| `m/{case}-{HHMM}-{hash}.html` | the maps the page loads; the hash changes when a map changes, so they are cached for a year |
| `maps/{case}-{HHMM}.html` | the same maps at stable addresses, for old links; opened on their own they show an "unofficial estimate" banner linking home |
| `_headers` | response headers (read by Cloudflare, not served): CSP, frame-ancestors, HSTS, nosniff, referrer and permissions policies, `noindex` on maps, long caching on `m/`, and a UTF-8 charset for `llms.txt` |
| `robots.txt`, `sitemap.xml`, `llms.txt`, `og.png` | crawler, AI-reader and link-preview files |
| `favicon.svg`, `favicon.ico`, `apple-touch-icon.png` | site icons from `make_icons.py`: "Pb" (lead's chemical symbol) in amber on the header slate; the 180 px home-screen icon adds the atomic number 82 so it reads as a periodic-table cell. Rerun the script only to change the design |
| `brand/profile.svg`, `brand/profile-{400,1024,2048}.png` | profile images for social media and GitHub, also from `make_icons.py`; the mark is shrunk to fit a circular crop |

On screens under 820 px the page scrolls as one: the header scrolls away, the map frame
grows to the map page's full height (the map page reports it by `postMessage`), and the map
is sized from the small viewport height (`100svh`, passed in the frame URL as `#h=`) so the
browser's address bar never covers it. A bar fixed to the bottom ("Map · What it shows ·
Questions") jumps between sections. On touch screens one finger scrolls the page and two
fingers move or zoom the map, with a short hint after a one-finger swipe. The technical
panel sections fold into "Model details", closed on narrow screens. Desktop keeps the sticky
header and a full-height map.

On the live site, `.html` addresses redirect to the address without it, so the page asks
for `m/...` without the extension; on a local server or `file://` it adds `.html`.

Third parties: map tiles load from Esri, and Cloudflare Web Analytics (cookieless) is
injected by Cloudflare. Both are named in the page's privacy note and allowed in the CSP.
Settings in the Cloudflare dashboard, not in this repo: **Always Use HTTPS**, and a
redirect from `www` to the bare domain.

### Search and AI-readable text

Most crawlers, and nearly all AI crawlers, don't run JavaScript, so the map itself is
invisible to them. Each build also writes plain text from the map data
(`forecast_summary.py`):

- **"What the forecast shows"** section under the map: why the date is Monday (with the
  Army citation), wind and cloud path with nearby towns, how far each EPA dust-lead level
  reaches per case, towns inside the yellow zone, air levels against PAC-1, and how sure
  the estimate is. Distances follow the U.S./metric switch.
- **Questions** section, repeated as FAQPage structured data (JSON-LD) next to the WebPage
  data.
- **`llms.txt`** at the site root with the same facts and the sources.
- Head tags: title, description, canonical, Open Graph/Twitter card with `og.png`;
  `robots.txt` allows all crawlers and lists `sitemap.xml`; the map files are `noindex`.

- **References** pop-over (link next to "What the forecast shows"): one alphabetical list
  in AMS author-date style (the format of the dispersion and meteorology literature it
  draws on) covering the event, the dispersion and deposition methods, the release-fraction
  sources, the levels of concern, weather data and software, then data and map credits, a
  key-assumptions table with in-text citations, and a suggested citation for the site. Edit the entries in `works_cited.py`; each was
  checked against the publisher, a library index or the issuing agency on Nov. 20, 2026.

Every statement repeats that this is an unofficial estimate and to follow official
instructions, since answer engines quote sentences out of context. The towns list
(`TOWNS` in `forecast_summary.py`) uses approximate town centers; add towns there.

## Writing style for the site

Everything the public reads (page header, About box, summary, FAQ, References, map labels,
`llms.txt`) follows these rules. The copy lives in `make_map_picker.py` (header, About box),
`forecast_summary.py` (`ABOUT_WHO`, `CAVEAT`, `WHY_MONDAY`, `time_note`, summary, FAQ,
`llms.txt`), `works_cited.py` (References), and `../../template.html` (map UI).

**Language**
- American English spelling and usage: center, color, labeled, traveled; "a.m." and "p.m.";
  "Nov. 20" in running text; "U.S." with periods.
- Plain, everyday words and short sentences. It should read like a person wrote it, not a
  form or a press release. Avoid stock phrases such as "independent screening model",
  "not affiliated with", "provided as is", and "leverage".
- Say "detonation" in formal text and "blast" in short UI labels. Say "lead in the air" and
  "lead on the ground" rather than "airborne fraction" or "deposition" where the public reads it.

- Use the active voice: say who does what ("the Army hasn't announced a time", "The site
  counts visits"), not "has not been announced" or "visits are counted". The owner chose to
  keep two sentences of the About box as written: "The Iowa Lead Tracker was made by a
  concerned Iowan…" and "…is intended to show what an open model should look like."

**Punctuation**
- Use the Oxford (serial) comma: "check, test, and improve"; "low, middle, high, and EPA
  permit".
- Put a comma after a state that falls mid-sentence ("Middletown, Iowa, and Fort Madison,
  Iowa"). Use semicolons in lists of places with states ("Wever, Iowa; Nauvoo, Ill.; and
  Hannibal, Mo.").
- Use AP state abbreviations in prose (Ill., Mo.), and don't double a period after one.

**Numbers and units**
- Round the way people say numbers: about 480 lb, 1,400 lb, 6,900 lb; 12 miles; 0.3 miles.
- U.S. units first, with the metric version behind the U.S./metric switch (`u-us` and
  `u-metric` spans). Air stays in µg/m³ and ground lead in µg/ft² in both modes, since
  those are the units the standards use.

**Tone and safety**
- Calm and factual, not alarmist. Never call a place "safe", and never tell people to
  evacuate or stay; point them to official instructions instead.
- Pair findings with the caveat that this is an unofficial estimate, not from the Army or
  any government agency (`CAVEAT`). Answer engines quote single sentences, so a finding shouldn't stand without it.
- Date anything that can change ("As of this update ..."), and cite a source for each
  outside fact.
- Don't name the site's author. Refer to them as "a concerned Iowan" or "a private
  citizen". Name other people only as cited authors or quoted officials.

**References**
- AMS author–date style in one alphabetical list, headed "References"; Federal Register
  entries as agency–year with the FR volume and page. Keep each entry checked against the
  publisher, a library index, or the issuing agency.

## Water misting and soil soaking

The Army's Nov. 18, 2026 advisory (https://d34w7g4gy10iej.cloudfront.net/pubs/pdf_78366.pdf)
says the soil over the bunkers will be saturated and water misters will run during the
blast. Neither is in the site's maps. The advisory gives no flow rates, layout, or drop
sizes, so every setup below is a guess, not a published figure.

**Inputs.** `--spray-flow` takes liters per minute. The sweep used round values a factor of
5 to 10 apart (2,000, 20,000, and 100,000 L/min) to see whether misting could matter at
all; the gal/min figures are conversions. For scale, one fire engine pumps roughly
1,000–1,500 gal/min, and 26,000 gal/min is about a large fireboat. Zone sizes and drop
sizes (1 mm sprinkler, 0.1 mm mist) are also guesses. Runs used the EPA permit 100% case,
noon, GFS, 2 hours (`--spray-flow`, `--spray-radius`, `--spray-height`, `--spray-drop`).

| Water flow | Wetted zone | Same as rain of | Drops | Lead captured |
|---|---|---|---|---|
| 528 gal/min (2,000 L/min) | 50 m radius, 30 m high | 15 mm/h | 1 mm | 0.1% |
| 528 gal/min | 50 m, 30 m | 15 mm/h | 0.1 mm | 0.7% |
| 5,283 gal/min (20,000 L/min) | 50 m, 30 m | 153 mm/h | 0.1 mm | 4.4% |
| 5,283 gal/min | 100 m, 60 m | 38 mm/h | 0.1 mm | 7.4% |
| 26,417 gal/min (100,000 L/min) | 100 m, 100 m | 191 mm/h | 0.1 mm | 19% |

"Lead captured" is the spray total divided by all lead lofted in that case.

**Method** (`puff_dispersal.py`, `slinn_efficiency`, `spray_coefficient`, and the spray
block in the puff loop):

1. Single-drop collection efficiency E from Slinn (1984) as given in Seinfeld and Pandis
   (2016): Brownian diffusion, interception, and inertial impaction. For lead-azide-density
   particles, E is about 0.02–0.03% for 0.3–1 µm particles with 1 mm drops and 0.3% with
   0.1 mm drops, but 93–98% at 10 µm (the "Greenfield gap" for fine particles).
2. Washout coefficient λ = 1.5 · J · E / D, where J is the water flux (m/s) over the zone
   and D the drop diameter. λ scales linearly with flow.
3. The zone is a square of the same area as the chosen circle, from the ground to the spray
   height, with uniform spray. Each 30 s step is split into 24 sub-steps; at each one, the
   share of each puff inside the box (Gaussian overlap in x, y, and z, with a ground image)
   loses 1 − exp(−λ·τ). Captured lead is deposited in the zone.

**What it leaves out**, all of which make misting look more effective than it likely is:
one drop size falling at terminal speed (real mist drifts and evaporates), even coverage
(real misters are lines or rings with gaps), and no interaction with the blast itself.
The conclusion that misters barely touch breathable-size lead is robust; the exact
percentages are not.

The cloud rises to about 820 ft within seconds and crosses the wetted zone in under a
minute, and drops catch 0.3–1 µm particles poorly. Soaking, the earth cover, and the sand
barriers act before the lead is airborne, so they belong in the airborne share (the four
cases), not in the spray option. If the Army publishes its mister flow, layout, and drop
size, add a case with those values. The page says this in one paragraph (`MISTING` in
`forecast_summary.py`).

## Why the numbers move between forecast updates

Comparing the Nov. 20 1:11 a.m. and 4:10 a.m. pulls for the same run (EPA permit case,
noon blast): ground winds dropped about 15–20% (8.4 to 6.9 mph in the first hour), and the
evening went from overcast to clear. Lighter wind raised the peak air and ground values
by about 20–30% (highest one-hour air average 876 to 1,145 µg/m³). The clear sunset made
the air near the ground stable (class F) and shrank the mixing layer from about 525–600 ft
to 260–350 ft just as the cloud was 60–100 miles south, so more lead settled there.
(Those runs predate the residual layer below, which removed most of that evening effect.)

**Residual layer (added Nov. 20, 2026).** The model used to fold the whole cloud into the
shallow night layer when the mixing height fell, which overstated ground-level air and
deposition downwind after sunset. Now the part above the new top stays aloft (see
"Residual layer" in `MODEL.md`). Same forecast (Nov. 20, 4:10 a.m. pull), GFS, noon:

| Case | Zone | Before | After |
|---|---|---|---|
| EPA permit | yellow (5 µg/ft²) | 99 mi | 91 mi |
| EPA permit | orange (40 µg/ft²) | 68 mi | 24 mi |
| EPA permit | red (100 µg/ft²) | 48 mi | 9.5 mi |
| EPA permit | one-hour air above PAC-1 | 91 mi | 23 mi |
| High | yellow | 94 mi | 65 mi |
| Middle | yellow | 80 mi | 38 mi |
| Low | yellow | 61 mi | 13 mi |

Near the plant nothing changed: the highest air and ground values are the same, because
the mixing layer is still about 2,500 ft deep for the first three hours. In the default
map, the highest ground-level air value at 5–6 p.m. fell from about 75 to 15–19 µg/m³, and
dry deposition by 8 p.m. fell from 21% to 10.5% of the lead; the rest stays aloft. A few
"any forecast" reaches grew slightly (for example middle-case PAC-1, 24 to 29 mi), because
less lead deposits early and more is left to travel. `--no-residual-layer` restores the old
behavior for comparison.


Far downwind the ground lead is a long, flat band close to the 5, 40 and 100 µg/ft² lines,
so a 20–30% change can move a contour tens of miles: the low case's yellow reach went from
10 to 56 miles at noon while its highest ground value only rose from 110 to 131 µg/ft².
The page says so in one sentence (`REACH_NOTE` in `forecast_summary.py`) and also shows the
farthest reach in any of the five forecasts.

## Open-Meteo limits

Open-Meteo's free API allows about 10,000 requests a day per IP address, and counts a
request for many locations or variables as several. A six-model run for one start
time costs a few hundred.

- Every response is cached in `met_cache/`, so repeating a run costs nothing.
- If you see "Daily API request limit exceeded", wait for the daily reset or run from
  another network. The cloud sandbox this was built in shares its address with other
  users and ran out several times.
- Move or delete `met_cache/map_met_all.json` to download fresh forecasts (see below).

## Refreshing on the day

Forecasts improve as the event approaches. The page and `met_cache/map_met_all.json`
(`__fetched__`) say when the saved ones were downloaded.

1. Run `python3 tools/refresh_forecast.py` from the repository root. It moves the saved
   file into a dated `met_cache_retrieved_*` folder, downloads new forecasts, rebuilds the
   site and regenerates the golden test numbers. It exits with status 3, keeping the
   saved file, if the forecasts haven't changed.
2. Check the news for the dated statements and open a pull request. Merging it deploys
   both sites (`.github/workflows/deploy.yml`).
3. RRFS is first in the list and takes over from GFS as soon as it covers the whole run.
   HRRR (18 to 48 hours ahead depending on the cycle) is in the spread but not shown.

`.github/workflows/refresh-forecast.yml` does step 1 every hour through
Wednesday, Nov. 25, and pushes the result to the `forecast-refresh` branch with a pull request. It
never deploys; merging the pull request does.

### More than one day

`DAYS` in `make_map_picker.py` lists the days the main site models (Monday, Nov. 23 and
Tuesday, Nov. 24), each with the same blast times. The page gets a "Day" menu, links carry
the day (`#1200-permit-tue`; links without one open Monday), and the summary, FAQ and
`llms.txt` add an "If the blasts are on Tuesday" section. Monday's maps keep their old
file names; other days' are prefixed with the date.

The forecast list puts RRFS first and GFS second: the first model with data for the whole
run is shown, so Monday shows RRFS and Tuesday shows GFS until RRFS reaches that far.

A day is built only if the saved forecasts include it (a refresh, which starts with no
saved file, downloads every day). So adding a day changes nothing until the next refresh,
and a deploy never has to download weather.

The staged page (`staged.py`, below) also has Tuesday, but with GFS and ECMWF only and its own
saved forecasts, so its Tuesday numbers differ from the main site's.

### Staged Tuesday/Wednesday maps

`staged.py` builds a separate set of maps for blasts on Tuesday, Nov. 24 and Wednesday,
Nov. 25, 11 a.m. to 1 p.m. every 30 minutes, all four cases, with only GFS and ECMWF
(GFS shown, ECMWF as the weather-model spread). They sit in their own folder on the main
site (`staged.DIR_NAME`), which nothing links to; the pages and the folder are noindex,
and the sitemap, robots.txt, `llms.txt` and the GitHub Pages mirror leave them out.
**Not private:** this repository is public, so the address is in it.

Their forecasts are saved in `met_cache/staged_forecasts.json`, which the hourly refresh
doesn't touch. Their own workflow refreshes them every hour through Wednesday, Nov. 25,
or by hand: Actions → "Refresh staged forecast" → Run workflow
(`.github/workflows/refresh-staged.yml`, which runs `tools/refresh_forecast.py
--staged`). It opens a pull request on the `forecast-refresh-staged` branch; merging it
deploys. Until that file exists, the build makes no staged maps. Locally,
`python3 staged.py --build` builds only these maps.

## Limits

- The share of lead that gets airborne is the largest unknown; the three release cases
  bracket it (see below).
- The 1 p.m. and 2 p.m. maps in `outputs/` are
  from the Friday, Nov 20 forecasts at the old location, with the old 20%-respirable case.

## Release cases: research notes

The model has to guess how much of the lead gets into the air and how big the pieces are.
The site shows three cases. In each, the share of lead below is airborne in breathable
"fume" sizes (0.3 to 10 µm), and the rest stays at the site.

| Site label | `--release-case` | Lead airborne | Pounds of lead (9,700 lb lead azide) | Basis |
|---|---|---|---|---|
| Low | `ap42-floor` | 7% | about 480 | lowest share consistent with EPA AP-42 blasting-cap tests |
| Middle | `fine-20` | 20% | about 1,380 | in between |
| High | `tnt-fine` | 55% | about 3,800 | DOE-HDBK-3010 rule: respirable mass equal to the TNT equivalent |
| EPA permit | `permit-100` | 100% | about 6,900 | emission factor 1.00 that EPA's Nov. 13, 2026 emergency permit (Appendix B) requires for the Army's plume maps; EPA calls it conservative |

Lead azide, Pb(N3)2, is 71.1% lead by weight, so 9,700 lb holds about 6,900 lb of lead.

### Amount and setup: sources

- **9,700 lb in 68 barrels:** Army Sustainment Command spokesperson Justine Barati, quoted in
  Deliso and Volack, "Army postpones plan to detonate nearly 10,000 pounds of lead azide until
  Monday," ABC News, 19 Nov 2026,
  https://abcnews.com/US/iowa-army-plant-lead-azide-detonation/story?id=138261613. Iowa Public
  Radio and Earthjustice attribute 9,500 lb to the Army; news coverage rounds to "5 tons".
- **68 drums:** EPA Region 7 emergency permit, 13 Nov 2026, pp. 2 and 12 (weight redacted),
  https://www.epa.gov/system/files/documents/2026-11/iaaap-emergency-permit-for-treatment-and-storage-final_redacted.pdf.
  The same permit: drums stay in the earth-covered magazines and are "detonated simultaneously
  or in rapid succession"; Appendix B requires SHARC, HPAC or a NARAC model with an emission
  factor of 1.00, an air edge of 0.18 µg/m³, and ground lines at 5 and 100 µg/ft² (stay indoors;
  also wet-clean); weather limits bar surface wind under 1 or over 15 mph, winds over 30 mph at
  1,000-3,000 ft, rain, storms, fog, overcast under 2,000 ft, night, and inversions.
- **Two detonations Monday at approximately noon:** Iowa HHS fact sheet for Nov. 23 (revised Nov. 20, 10:36 a.m.),
  https://hhs.iowa.gov/media/19822/download?inline=.
- The Army's FAQ, open house slides and environmental handout (linked from
  https://response.epa.gov/site/site_profile.aspx?site_id=17211) give no weight.

### DOE-HDBK-3010 (nuclear handbook)

- DOE-HDBK-3010-94 (reaffirmed 2013), *Airborne Release Fractions/Rates and Respirable
  Fractions for Nonreactor Nuclear Facilities*. Its values come from experiments on how
  spills, fires and explosions loft material, many with non-radioactive stand-ins, so the
  physics carries over to lead.
- Source term = material at risk × damage ratio × airborne release fraction × respirable
  fraction × leak path factor.
- For detonations next to inert solids, a respirable release equal to the TNT-equivalent
  mass (capped at 100%) bounds the Steindler and Seefeldt (1980) data. For this scenario:
  about 3,800 lb TNT equivalent against about 6,900 lb of lead, so 55%.
- Poor fit: the handbook's blast data are for inert material shattered by a nearby
  charge. Here the lead azide *is* the explosive; it breaks down into lead and nitrogen
  at high temperature, and much of the lead likely condenses into fine fume.
- **Unverified:** the earlier `20-percent` case was described as "the general
  upper-bound precedent quoted in DOE-HDBK-3010", and the site once said past tests ranged
  "from under 1% to about 22%". Neither number was found in the handbook during a search
  on Nov 20, 2026. The site no longer uses either wording.

### EPA AP-42 Chapter 15 (ordnance detonation tests)

Army and EPA emission tests of real ordnance. Batches of 5 to 25 items were set off in a
sealed test chamber at Aberdeen Proving Ground, and the air was sampled for particulate
(TSP, PM-10, PM-2.5) and metals (lead by a modified 40 CFR 50 Appendix G method).
Factors are given per item and per pound of net explosive weight (NEW). The blasting-cap
sections are still drafts.

Blasting caps (report EO 07, Feb 2008; M15 from EO 11, Oct 2008):

| Item | NEW per item (lb) | Lead (lb/item) | Lead (lb per lb NEW) | Lead share of TSP | PM-10 / TSP | PM-2.5 / TSP |
|---|---|---|---|---|---|---|
| M6 electric cap | 0.00292 | 1.5e-4 | 0.051 | 37% | 98% | 59% |
| M7 non-electric cap | 0.00276 | 2.6e-4 | 0.095 | 51% | 96% | 67% |
| M11 cap, 30-ft shock tube | 0.00273 | 1.3e-4 | 0.048 | 27% | 96% | 60% |
| M12 cap, 500-ft shock tube | 0.00618 | 5.3e-5 | 0.0086 | 21% | 88% | 48% |
| M13 cap, 1,000-ft shock tube | 0.0111 | 5.5e-5 | 0.0050 | 20% | 93% | 59% |
| M14 time-delay cap | 0.0259 | 3.8e-5 | 0.0015 | 2% | 100% | 100% |
| M15 time-delay cap | 0.0042 | 1.8e-4 | 0.043 | 47% | 97% | 71% |

Fuzes, for comparison (more metal from other parts): M557 point-detonating fuze 0.0057 lb
lead per lb NEW, M739A1 0.0022, M582 MTSQ fuze 0.0094.

What this means for the model:

1. **The airborne lead is almost all breathable.** 96–98% of the dust from the plain caps
   was PM-10 and about 60–70% was PM-2.5, and lead was a large share of that dust. The
   earlier `20-percent` case put 80% of the lead in coarse 30 and 100 µm pieces; the
   tests show almost no coarse dust staying airborne. The new cases put all airborne lead
   in fume sizes.
2. **At least 7% of the lead got airborne.** If a cap were pure lead azide it would hold
   0.711 lb of lead per lb NEW. Measured lead of 0.048–0.095 lb per lb NEW for the plain
   caps (M6, M7, M11) means at least 7–13% of their lead got airborne. Real caps hold other
   explosives too, so the true share is higher; the reports don't give each cap's lead
   azide content, so how much higher is unknown. The low case uses 7%.
3. **Caveats.** The caps were set off in the open inside a chamber; earth-covered charges
   should trap more lead in the crater and soil. Some measured lead may come from parts
   other than lead azide. Tests of 5 to 25 small items may not scale to 10,000 lb.

## Threat-zone levels: research notes

The map's "Levels of concern" view starts on lead deposited on the ground, because EPA's
cleanup levels are for lead on surfaces. The air levels are still there in the zone menu.

**Ground (default).** EPA dust-lead action levels, 40 CFR 745.227(e)(8)(viii), in force
from Jan. 12, 2026 (they replaced 10, 100 and 400 µg/ft²):

| Zone | Level | What it is |
|---|---|---|
| Yellow | 5 µg/ft² (53.8 µg/m²) | floors |
| Orange | 40 µg/ft² (431 µg/m²) | interior window sills |
| Red | 100 µg/ft² (1,076 µg/m²) | window troughs |

These are for indoor dust measured by wipe tests, so lead falling outdoors is only a rough
comparison. The page says so under the zone table. The U.S./metric switch shows them in
µg/ft² or µg/m².

**Air.** Compared against the highest 60-minute average:

| Zone | Level | What it is |
|---|---|---|
| Yellow | 0.15 µg/m³ | lead NAAQS (rolling 3-month average; set 2008, kept 2016) |
| Orange | 1.5 µg/m³ | the 1978 lead NAAQS (quarterly average) |
| Red | 32 µg/m³ | DOE PAC-1 for lead, 60 minutes |

The NAAQS levels are long-term averages, so an hour above them is not a violation.

DOE Protective Action Criteria come from the DOE PAC/TEEL database
(https://emhub1.energy.gov/pacteel). The values below come from the
export (`PacData.xlsx`, last modified Dec. 3, 2025), which is available from that site. Lead entries, in mg/m³:

| Substance | CASRN | PAC-1 | PAC-2 | PAC-3 |
|---|---|---|---|---|
| Lead | 7439-92-1 | 0.032 | 120 | 700 |
| Lead oxide (PbO) | 1317-36-8 | 0.034 (0.032 as lead) | 130 | 750 |
| Lead azide | 13424-46-9 | not listed | | |

- PAC-1 is mild, short-lived effects; PAC-2 serious or lasting harm; PAC-3 danger to
  life. All are 60-minute levels.
- NOAA's CAMEO Chemicals page for lead (https://cameochemicals.noaa.gov/report?key=CH16140)
  lists PAC-1 as 0.15 mg/m³, citing "DOE, 2024". That doesn't match the DOE database,
  which is the primary source, so the map uses 0.032 mg/m³.
- Highest modeled air levels (any blast time, Monday forecast): 60-minute average 73, 210
  and 578 µg/m³ for the low, middle and high cases. PAC-1 is crossed near the plant in all
  three; PAC-2 (120,000 µg/m³) is never reached. That's why the air zones use the NAAQS
  levels for yellow and orange rather than PAC-2 and PAC-3.

Other sources: EPA NAAQS table (https://www.epa.gov/criteria-air-pollutants/naaqs-table),
40 CFR 745.227 (https://www.ecfr.gov/current/title-40/part-745/section-745.227), and the
Nov. 12, 2024 Federal Register rule
(https://www.federalregister.gov/documents/2024/11/12/2024-25070/reconsideration-of-the-dust-lead-hazard-standards-and-dust-lead-post-abatement-clearance-levels).

## Release-case sources

- DOE-HDBK-3010-94: https://www.energy.gov/sites/prod/files/2018/02/f48/DOE%202013_HDBK-3010-94%20Airborne%20Release%20Fractions_0.pdf
  (NRC copy: https://www.nrc.gov/docs/ML1307/ML13078A031.pdf)
- AP-42 Chapter 15 index: https://www.epa.gov/air-emissions-factors-and-quantification/ap-42-fifth-edition-volume-i-chapter-15-ordnance
- AP-42 Ch. 15 background, EO 07 blasting caps (Feb 2008 draft): https://www.epa.gov/sites/default/files/2020-11/documents/b15_eo7_draft_feb08.pdf
- AP-42 Ch. 15 background, EO 05 fuzes and incendiaries: https://www.epa.gov/sites/default/files/2020-11/documents/b15_eo5.pdf
- AP-42 Ch. 15 background, EO 11 incl. M15 cap (Oct 2008 draft): https://www.epa.gov/sites/default/files/2020-11/documents/b15_eo11_draft102008.pdf
- AP-42 Section 15.8 draft, signals and simulators: https://gaftp.epa.gov/ap42/ch15/s08/draft/d15s08.pdf
