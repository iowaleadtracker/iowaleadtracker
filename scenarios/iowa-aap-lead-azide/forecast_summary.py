"""Plain-text facts about the forecast, read from the built maps.

They feed the site's summary section, its FAQ structured data, and llms.txt. Used by
make_map_picker.py.

Everything here is computed from the map shown by default in each file (the first
weather model that covers the run), so it matches what a visitor sees.
"""

from __future__ import annotations

import base64
import datetime as dt
import html
import json
import math
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeAlias

import numpy as np
import numpy.typing as npt
from works_cited import (
    ANALYSIS_PATH,
    ANALYSIS_URL,
    CONTACT_TEXT,
    INSTAGRAM_HANDLE,
    INSTAGRAM_URL,
    SOURCE_URL,
)

Facts: TypeAlias = dict[str, Any]
FloatArray: TypeAlias = npt.NDArray[np.float64]

# Unit conversions (exact definitions, except the degree length).
M2_PER_FT2 = 0.09290304
KG_M2_PER_UG_FT2 = 1e-9 / M2_PER_FT2
MI = 1.609344  # km per mile
KG_PER_LB = 0.45359237
M_PER_FT = 0.3048
MPH_PER_M_S = 2.23694
KM_PER_DEG_LAT = 111.195  # mean Earth radius 6371 km x pi/180

# EPA dust-lead action levels, ug/ft^2 (40 CFR 745.227): floors, window sills, troughs.
DEP_LEVELS = [("yellow", 5), ("orange", 40), ("red", 100)]
DEP_COLORS = [k for k, _ in DEP_LEVELS]
PAC1_KG_M3 = 32e-9  # DOE PAC-1 for lead, 32 ug/m^3 over 60 minutes (DOE 2025)
# EPA emergency permit weather limits (EPA 2026): surface wind 1-15 mph, at most 30 mph
# at 1,000-3,000 ft, no rain.
PERMIT_SFC_MPH = (1, 15)
PERMIT_ALOFT_MPH = 30
PERMIT_ALOFT_M = (1000 * M_PER_FT, 3000 * M_PER_FT)
NEAR_TOWN_KM = 8 * MI  # a path point is "near" a town within 8 miles
SPREAD_SHOWN = 1.05  # show "up to ... in any forecast" when the spread adds over 5%
NOON = (12, 0)

# Towns near the plant and downwind, as (name, latitude, longitude). Approximate centers.
TOWNS = [
    ("Middletown, Iowa", 40.829, -91.264),
    ("Burlington, Iowa", 40.808, -91.113),
    ("Danville, Iowa", 40.861, -91.315),
    ("West Burlington, Iowa", 40.825, -91.157),
    ("Wever, Iowa", 40.711, -91.233),
    ("West Point, Iowa", 40.716, -91.451),
    ("Fort Madison, Iowa", 40.630, -91.315),
    ("Donnellson, Iowa", 40.643, -91.565),
    ("Montrose, Iowa", 40.531, -91.416),
    ("Keokuk, Iowa", 40.397, -91.385),
    ("New London, Iowa", 40.927, -91.400),
    ("Mount Pleasant, Iowa", 40.964, -91.551),
    ("Mediapolis, Iowa", 41.008, -91.164),
    ("Nauvoo, Ill.", 40.550, -91.385),
    ("Dallas City, Ill.", 40.636, -91.163),
    ("Hamilton, Ill.", 40.396, -91.339),
    ("Warsaw, Ill.", 40.359, -91.434),
    ("Carthage, Ill.", 40.416, -91.136),
    ("Oquawka, Ill.", 40.932, -90.947),
    ("Macomb, Ill.", 40.459, -90.672),
    ("Quincy, Ill.", 39.936, -91.410),
    ("Kahoka, Mo.", 40.420, -91.719),
    ("Alexandria, Mo.", 40.359, -91.457),
    ("Canton, Mo.", 40.125, -91.625),
    ("La Grange, Mo.", 40.042, -91.497),
    ("Palmyra, Mo.", 39.794, -91.523),
    ("Hannibal, Mo.", 39.708, -91.358),
]
TOWN_ORDER = {name: i for i, (name, _, _) in enumerate(TOWNS)}
# 16-point compass, clockwise from north, with the words used in sentences.
WORDS = {
    "N": "north",
    "NNE": "north-northeast",
    "NE": "northeast",
    "ENE": "east-northeast",
    "E": "east",
    "ESE": "east-southeast",
    "SE": "southeast",
    "SSE": "south-southeast",
    "S": "south",
    "SSW": "south-southwest",
    "SW": "southwest",
    "WSW": "west-southwest",
    "W": "west",
    "WNW": "west-northwest",
    "NW": "northwest",
    "NNW": "north-northwest",
}
COMPASS = list(WORDS)
MODEL_SHORT = {
    "gfs_global": "GFS",
    "gfs_seamless": "GFS",
    "ncep_hrrr_conus": "HRRR",
    "ncep_rrfs_conus": "RRFS",
    "ecmwf_ifs025": "ECMWF",
}

ARMY_URL = "https://www.army.mil/article/296926"
# Said wherever towns are listed, so a list is never read as a town-by-town verdict.
TOWN_CAVEAT = (
    "A place outside the shaded area may still get lead, and a place inside it may get "
    "none you could measure."
)
ARMY_CITE = 'Army Sustainment Command, "Postponed: Lead Azide Detonation," army.mil, Nov. 19, 2026'
WHY_MONDAY = (
    "On Nov. 19, 2026, the Army postponed the controlled detonation at the Iowa Army "
    "Ammunition Plant from Friday, Nov. 20, to Monday, Nov. 23. The Acting Secretary of the "
    "Army moved it \u201cuntil the latest possible moment prior to a forecasted temperature "
    "drop,\u201d which \u201cwould risk further destabilization of the material.\u201d"
)
# The government's notice to the 8th Circuit (No. 26-3374), filed Nov. 21, 2026: "the Army
# intends to act by November 24, 2026" (p. 1), "intends to act on November 24, 2026" (p. 6),
# "by November 24, 2026" (p. 7). KCCI reported it Nov. 22. Its response to the stay motion,
# filed Nov. 22 (Entry 5708599; read in full Nov. 23): "The Army postponed the planned
# detonation to November 23, 2026, and then to November 24" (p. 9); "the Army intends to act
# on November 24, 2026" (p. 10); the permit has the Army update its air dispersion estimate
# "at least 48 hours before treatment, and begin hourly updates six hours before
# detonation" (pp. 7-8).
WHY_TUESDAY = (
    "In a court filing on Nov. 22, 2026, the government said the Army postponed the "
    "controlled detonation again, to Tuesday, Nov. 24, and intends to act that day. "
    "(Its Nov. 21 filing had said \u201cby\u201d Nov. 24.)"
)
# The Army's own announcement (verified U.S. Army account on Facebook, Nov. 22, 2026, about
# 7:45 p.m. CST; text checked from the maintainer's screenshot). The post's permalink, from
# the maintainer, without tracking parameters (not a personal "share" link).
ARMY_WED_URL = "https://www.facebook.com/story.php?story_fbid=1611961230959211&id=100064360494281"
ARMY_WED_CITE = "U.S. Army on Facebook, Nov. 22, 2026"
WHY_WEDNESDAY = (
    "Late on Nov. 22, the Army said the controlled detonation \u201cis now scheduled on "
    "Wednesday, November 25, 2026 to allow for optimal weather conditions and all mitigation "
    "measures to be emplaced.\u201d"
)
WEDNESDAY_SOURCE_HTML = f'<a href="{html.escape(ARMY_WED_URL)}" rel="noopener">{ARMY_WED_CITE}</a>'
WEDNESDAY_SOURCE_TEXT = f"{ARMY_WED_CITE}, {ARMY_WED_URL}"
# President Trump's Truth Social post of Monday, Nov. 23, 2026, as quoted by KCRG (published
# 12:29 p.m. CST, updated 12:36 p.m.; read in full on the page Nov. 23, 2026). KCRG: "The Army
# had no immediate comment when asked about the president's social media post." It gave no
# new date; the Army had planned Wednesday. The Army Secretary's post that evening did.
# The Acting Secretary of the Army's post on X (@SecArmy, pinned; posted the evening of
# Nov. 23, 2026, after the 8th Circuit's order; text checked from the maintainer's
# screenshot, taken about 11 p.m. CST when the post was 2 hours old). The post's permalink,
# from the maintainer, without its tracking parameter. It gives no clock time.
SECARMY_URL = "https://x.com/SecArmy/status/2125060405605154940"
SECARMY_CITE = "Acting Secretary of the Army on X, Nov. 23, 2026"
SECARMY_MORNING = (
    "On the evening of Nov. 23, the Acting Secretary of the Army said the Army will proceed "
    "with \u201can extensively mitigated, carefully controlled detonation, which will occur "
    "this Wednesday morning, as previously scheduled, based on forecast wind conditions.\u201d"
)
TRUMP_URL = "https://www.kcrg.com/2026/11/23/president-trump-orders-military-pause-iowa-detonation/"
TRUMP_CITE = "KCRG, Nov. 23, 2026"
TRUMP_HOLD = (
    "On Monday, Nov. 23, President Trump said on Truth Social that he has \u201cordered the "
    "Military not to do so until such time as the Eighth Circuit agrees that we can go "
    "forward,\u201d and that the decision is \u201cfully subject to the incoming Governor "
    "Elect, Rob Sand, agreeing to the operation.\u201d Later that day, the 8th Circuit "
    "cleared the way for the detonation (see Court case). Sand didn\u2019t directly say "
    "whether he approved, Iowa Public Radio reported; he said \u201cthe Administration should "
    "make this decision based on the information they have from the people they brought in "
    "to do the job months ago and have been on the ground in Middletown for weeks.\u201d The "
    "Army had no immediate comment on the ruling or the president\u2019s post, the Associated "
    "Press reported. " + SECARMY_MORNING
)
PERMIT_URL = (
    "https://www.epa.gov/system/files/documents/2026-11/"
    "iaaap-emergency-permit-for-treatment-and-storage-final_redacted.pdf"
)
PERMIT_CITE = "EPA Region 7 emergency permit for the Iowa Army Ammunition Plant, Nov. 13, 2026"
# Who made the map and why (About box, FAQ, llms.txt).
ABOUT_WHO = (
    "The Iowa Lead Tracker was made by a concerned Iowan, not by the Army or any government "
    "agency, out of frustration that the Army hadn\u2019t released the inputs, data, or model "
    "runs behind the public safety maps for its planned lead azide detonation. On Nov. 24 the "
    "Army published its estimate (an emission factor of 0.26 for the mitigated blast), but "
    "not the model inputs or runs behind it. The Iowa "
    "Lead Tracker is intended to show what an open model should look like. When the public "
    "relies on a forecast to stay safe, others should be able to check, test, and improve it."
)
# Moved out of ABOUT_WHO into the About box's safety paragraph (owner's choice, Nov. 20, 2026).
NOT_CHECKED = (
    "The U.S. Army, the Iowa Army Ammunition Plant, and government agencies didn\u2019t make "
    "this map, and none of them have checked it."
)
ADVISORY_URL = "https://d34w7g4gy10iej.cloudfront.net/pubs/pdf_78366.pdf"
# The Eighth Circuit's order, as reported by Iowa Public Radio (Nov. 20, 2026, 11:45 a.m. CST).
COURT_URL = (
    "https://www.iowapublicradio.org/ipr-news/2026-11-20/"
    "court-injunction-army-planned-lead-azide-detonation"
)
COURT_CITE = "Iowa Public Radio, Nov. 20, 2026"
# The 8th Circuit's ruling of Monday, Nov. 23, 2026, as reported by the Associated Press on
# KCRG (published 5:04 p.m. CST; read in full on the page Nov. 23): "A federal appeals court
# on Monday cleared the way for the U.S. Army to detonate several tons of degraded
# bomb-making material at an Iowa ammunition plant." "The Army had no immediate comment
# about the court ruling or the president's social media post."
RULING_URL = (
    "https://www.kcrg.com/2026/11/23/"
    "federal-appeals-court-clears-way-us-army-detonate-degraded-bomb-making-material-iowa/"
)
RULING_CITE = "Associated Press on KCRG, Nov. 23, 2026"
#: The court case in one sentence, for the About box (the full timeline, COURT_HOLD, is in
#: the Methodology and References dialog). From the AP report above.
COURT_SHORT_HTML = (
    "On Monday, Nov. 23, the 8th U.S. Circuit Court of Appeals cleared the way for the Army "
    f'to detonate the lead azide (<a href="{RULING_URL}" rel="noopener">{RULING_CITE}</a>). '
    "The full timeline and its sources are under Methodology and References."
)
# The same ruling, and Gov.-elect Rob Sand's Nov. 23 post, as reported by Iowa Public Radio
# (published Nov. 22, 2026, 9:11 p.m. CST, "updated Monday afternoon"; read in full from the
# maintainer's copy, saved Nov. 23, 9:16 p.m.). "In a Monday order, judges lifted the stay";
# "The ruling also found the Iowa Environmental Council and Sierra Club hadn't proven that the
# EPA and Army had not adequately considered other options"; "Sand did not directly say
# whether he approved of the detonation".
SAND_URL = (
    "https://www.iowapublicradio.org/ipr-news/2026-11-23/"
    "court-lifts-stay-block-iowa-lead-detonation"
)
SAND_CITE = "Iowa Public Radio, Nov. 23, 2026"
# The hold and the government's latest filing. The last sentence names the days the maps
# model, so it's built by court_pause() from the days actually built.
# Newest first (maintainer's choice, Nov. 22, 2026).
COURT_HOLD = (
    "On Monday, Nov. 23, 2026, the 8th U.S. Circuit Court of Appeals cleared the way for the "
    "Army to detonate the lead azide, the Associated Press reported. It lifted its hold on "
    "the EPA\u2019s emergency permit, finding that the Iowa Environmental Council and the "
    "Sierra Club\u2019s Iowa chapter hadn\u2019t proven that the EPA and the Army had not "
    "adequately considered other options, Iowa Public Radio reported. That evening, the "
    "Acting Secretary of the Army said the detonation would be Wednesday morning, as "
    "previously scheduled. "
    "Late on Nov. 22, the Army said the blasts are now scheduled for Wednesday, "
    "Nov. 25. Earlier that day, the government asked the 8th U.S. Circuit Court of Appeals "
    "to lift its hold on the EPA\u2019s emergency permit for the blasts and said the Army had "
    "postponed them to Tuesday, Nov. 24; the court hadn\u2019t ruled as of that filing. In a "
    "court filing on Nov. 21, the government said the Army intends to use an emergency "
    "exclusion in EPA\u2019s rules to detonate the lead azide without the permit, while "
    "following the permit\u2019s terms and its measures to limit lead dust. Late on Nov. 19, "
    "the court put the permit on hold until it rules on a request by the Iowa Environmental "
    "Council and the Sierra Club\u2019s Iowa chapter to block the blasts, Iowa Public Radio "
    "reported."
)


# The planned day (the Army's Nov. 22 announcement), which the summary leads with by
# default (facts()["day"] can name another), and the earlier day Iowa HHS gave "approximately
# noon" for. The window (WINDOW) is half an hour either side of the Army's and FEMA's 9 a.m.
PLANNED_DAY = "Wednesday, Nov. 25"
#: The blast times the maps model, in words; must match make_map_picker.TIMES and
#: staged.TIMES (tests/test_site.py checks).
WINDOW = "8:30 to 9:30 a.m."
WINDOW_HOURLY = "at 8:30, 9:00 and 9:30 a.m."
#: The blast time the site's own maps model since Nov. 26, in words; must match
#: make_map_picker.TIMES (tests/test_site.py checks). WINDOW and WINDOW_HOURLY above are
#: still the staged Wednesday-to-Friday page's times.
BLAST_TIME = "9 a.m."
HHS_DAY = "Monday, Nov. 23"


def day_num(day: str) -> int:
    """Return the day of the month in a label like "Tuesday, Nov. 24" (all are in November)."""
    return int(day.rsplit(" ", 1)[-1])


def window_note(day: str) -> str:
    """Say another day's maps use the same blast times ("" for the planned and HHS days).

    The planned day's time is covered by the time paragraph (TIME_HEAD, time_note).
    """
    if day in (PLANNED_DAY, HHS_DAY):
        return ""
    weekday = day.split(",", maxsplit=1)[0]
    return f"No time has been given for {weekday}, so these maps use the same {WINDOW} window."


SAME_WINDOW = window_note("Thursday, Nov. 26")


def court_pause(more_days: list[str] | None = None, first: str = PLANNED_DAY) -> str:
    """Return the court-hold paragraph, ending with the days the maps model, in date order."""
    days = sorted({first, *(more_days or [])}, key=day_num)
    named = days[0] if len(days) == 1 else ", ".join(days[:-1]) + ", and " + days[-1]
    return f"{COURT_HOLD} These maps model {named}."


COURT_PAUSE = court_pause()
# The filing itself (primary source), and KCCI's report of it (updated 7:55 a.m. CST, Nov. 22,
# 2026; headline, subheading and first paragraph checked by the maintainer on the page).
FILING_URL = (
    "https://s3.documentcloud.org/documents/28930203/"
    "iowa-environmental-council-v-us-environmental-protection-agency.pdf"
)
FILING_CITE = "Government notice, 8th Cir. No. 26-3374, Nov. 21, 2026"
# Its Nov. 22 response to the stay motion (RECAP copy on CourtListener; the maintainer's copy
# was read in full).
RESPONSE_URL = (
    "https://storage.courtlistener.com/recap/gov.uscourts.ca8.116088/"
    "gov.uscourts.ca8.116088.805661522.0.pdf"
)
RESPONSE_CITE = "Government response, 8th Cir. No. 26-3374, Nov. 22, 2026"
KCCI_URL = "https://www.kcci.com/article/lead-azide-bomb-detonation-iowa-tuesday/74499570"
KCCI_CITE = "KCCI, Nov. 22, 2026"
# The president's post (KCRG) and Sand's reply (Iowa Public Radio).
# The president's post (KCRG), the ruling and the Army's silence (AP), Sand's reply (IPR).
TRUMP_SOURCE_HTML = (
    f'<a href="{TRUMP_URL}" rel="noopener">{TRUMP_CITE}</a>; '
    f'<a href="{RULING_URL}" rel="noopener">{RULING_CITE}</a>; '
    f'<a href="{SAND_URL}" rel="noopener">{SAND_CITE}</a>; '
    f'<a href="{SECARMY_URL}" rel="noopener">{SECARMY_CITE}</a>'
)
TRUMP_SOURCE_TEXT = (
    f"{TRUMP_CITE}, {TRUMP_URL}; {RULING_CITE}, {RULING_URL}; {SAND_CITE}, {SAND_URL}; "
    f"{SECARMY_CITE}, {SECARMY_URL}"
)
# Newest first, like the paragraph.
COURT_SOURCES_TEXT = (
    f"{SECARMY_CITE}, {SECARMY_URL}; {RULING_CITE}, {RULING_URL}; {SAND_CITE}, {SAND_URL}; "
    f"{WEDNESDAY_SOURCE_TEXT}; "
    f"{RESPONSE_CITE}, {RESPONSE_URL}; "
    f"{FILING_CITE}, {FILING_URL}; {COURT_CITE}, {COURT_URL}"
)
COURT_SOURCES_HTML = (
    f'<a href="{SECARMY_URL}" rel="noopener">{SECARMY_CITE}</a>; '
    f'<a href="{RULING_URL}" rel="noopener">{RULING_CITE}</a>; '
    f'<a href="{SAND_URL}" rel="noopener">{SAND_CITE}</a>; '
    f"{WEDNESDAY_SOURCE_HTML}; "
    f'<a href="{RESPONSE_URL}" rel="noopener">{RESPONSE_CITE}</a>; '
    f'<a href="{FILING_URL}" rel="noopener">{FILING_CITE}</a>; '
    f'<a href="{COURT_URL}" rel="noopener">{COURT_CITE}</a>'
)
TUESDAY_SOURCES_TEXT = (
    f"{RESPONSE_CITE}, {RESPONSE_URL}; {FILING_CITE}, {FILING_URL}; {KCCI_CITE}, {KCCI_URL}"
)
# Sources cited in plain text as "Citation, URL". The visible FAQ shows each as a link
# on the citation (make_map_picker.linkify); JSON-LD and llms.txt keep the full address.
CITED_SOURCES = (
    (SECARMY_CITE, SECARMY_URL),
    (RULING_CITE, RULING_URL),
    (SAND_CITE, SAND_URL),
    (TRUMP_CITE, TRUMP_URL),
    (ARMY_WED_CITE, ARMY_WED_URL),
    (RESPONSE_CITE, RESPONSE_URL),
    (FILING_CITE, FILING_URL),
    (COURT_CITE, COURT_URL),
    (KCCI_CITE, KCCI_URL),
    (ARMY_CITE, ARMY_URL),
)
TUESDAY_SOURCES_HTML = (
    f'<a href="{RESPONSE_URL}" rel="noopener">{RESPONSE_CITE}</a>; '
    f'<a href="{FILING_URL}" rel="noopener">{FILING_CITE}</a>; '
    f'<a href="{KCCI_URL}" rel="noopener">{KCCI_CITE}</a>'
)
# Army mitigation, from the Nov. 24, 2026 public safety advisory (ADVISORY_NOV24_URL): "physical
# barriers full of sand that are approximately two stories high, a 'water wall' and gel blocks
# to contain particle dispersion, precise deployment of aqueous foam barriers ... Before and
# during the controlled detonation, the soil above and surrounding the earth-covered magazines
# will be thoroughly saturated with water by misters." Its "Mitigated 0.26" maps (ARMY_MAPS_PDF)
# are the Army's estimate with these measures. The model's own spray runs (README, "Water
# misting and soil soaking"): 0.1% at 528 gal/min up to 19% at 26,000 gal/min.
#
# The Nov. 24 news conference, as reported by Shaw Local (BRIEFING_URL) and KCCI
# (KCCI_BRIEF_URL), both read in full Nov. 25 (README "Nov. 24 briefing"): Col. Aaron Teller
# said "a vent opening was placed in the protective barriers ... to vent debris into three
# miles of uninhabited area"; "two walls of four 16,000-gallon water tanks around the
# bunkers"; a coffer dam "filled with aqueous foam concentrate 380"; on the magazine tops "a
# tarp; a containment screen specifically designed to contain lead ... and a layer of foam at
# least two feet thick." The advisory itself lists none of these.
BRIEFING_URL = (
    "https://www.shawlocal.com/news/2026/11/24/"
    "heres-how-army-plans-to-minimize-toxic-lead-dust-following-iowa-ammunitions-blast/"
)
BRIEFING_CITE = "Shaw Local, Nov. 24"
KCCI_BRIEF_URL = (
    "https://www.kcci.com/article/what-else-could-a-lead-azide-detonation-release-in-eastern-iowa/"
    "74526545"
)
KCCI_BRIEF_CITE = "KCCI, Nov. 24"
BRIEFING_SOURCES_HTML = (
    f'<a href="{BRIEFING_URL}" rel="noopener">{BRIEFING_CITE}</a>; '
    f'<a href="{KCCI_BRIEF_URL}" rel="noopener">{KCCI_BRIEF_CITE}</a>'
)
BRIEFING_SOURCES_TEXT = f"{BRIEFING_CITE}, {BRIEFING_URL}; {KCCI_BRIEF_CITE}, {KCCI_BRIEF_URL}"
MISTING = (
    "The Army said the blasts would be inside earth-covered concrete magazines, with sand "
    "barriers about two stories high, a \u201cwater wall\u201d and gel blocks, aqueous foam "
    "barriers, and the soil around the magazines soaked by misters before and during the "
    "blast. At a Nov. 24 news conference, the Army also described a vent in the barriers "
    "aimed at about 3 miles of the plant where no one lives, two walls of four 16,000-gallon "
    "water tanks, a dam around the magazines filled with foam, and a tarp, a screen to hold "
    "in lead, and at least 2 feet of foam on top of the magazines. "
    "The Army\u2019s estimate for this mitigated blast is an emission factor of 0.26 "
    "(26% of the lead airborne), the U.S. Army mitigated case here. This model can\u2019t "
    "represent the barriers, foam or gel; its own runs of water spray alone, at about 500 to "
    "26,000 gallons a minute, caught less than 1% to about 19% of the airborne lead."
)
# The 1977 figure is Teller's account at the Nov. 24 news conference (Shaw Local: "in 1977,
# when approximately 7,000 pounds of the material were exploded in open air in Colorado. With
# no mitigation efforts, Teller said only 25% of the lead particulate went into the
# atmosphere"; KCCI: "about 75% of the lead particulate stayed at the site and 25% entered the
# atmosphere"). No report of the 1977 blast has been found; the Army gave no reduction estimate.
PRECEDENT = (
    "Col. Aaron Teller, who leads the operation, said that the last time the Army disposed of a "
    "lead azide stockpile, about 7,000 pounds set off in the open in Colorado in 1977 with no "
    "mitigation, about 25% of the lead went into the air. The Army hasn\u2019t said how much "
    "its mitigation lowers that."
)
# README "Release point: sensitivity check" (tools/release_point_sensitivity.py).
RELEASE_POINT = (
    "The archived-weather maps start the cloud midway between the two magazines the blasts "
    "were in (40.8096, \u221291.2692). That place comes from a reader\u2019s tip checked "
    "against published imagery and video; no official source confirms it. The forecast maps "
    "start the cloud where they did before the blast, at one point for the plant about 1.1 "
    "miles to the north: the Army hadn\u2019t said exactly where the blasts would be, and "
    "it planned to vent them across part of the plant. Moving "
    "that point 2 or 3 miles changes how far the lead reaches only a little, but it can "
    "change which towns are inside the lines."
)
# The Army's public safety advisory of Nov. 24, 2026 (Lori McFate, Army Sustainment Command;
# read in full from the maintainer's PDF of the page, printed Nov. 24, 9:28 a.m. CST). Quoted
# or closely paraphrased in time_note: "on Wednesday, November 25, 2026 at approximately
# 9:00 a.m. CST"; "A more precise time will be communicated after evaluating changing weather
# patterns"; "FEMA is supporting the recommended relocation for all residents of Middletown,
# Iowa, and immediate surrounding impacted areas commencing on Tuesday, 24 November 2026.
# This defines the evacuation zone as a 5-mile cone extending southwest of IAAAP"; "the
# evacuation extends one mile beyond the dispersion path"; "Residents who live outside the
# recommended evacuation zone are encouraged to shelter in place. Best practices include
# closing all windows and doors"; "The FEMA Helpline is available for all individuals who
# have questions 24/7 at 1-800-621-3362"; maps "Six hours in advance of the detonation and
# every hour thereafter until the detonation".
ADVISORY_NOV24_URL = "https://www.army.mil/article/297039"
ADVISORY_NOV24_CITE = "Army public safety advisory, Nov. 24"
ARMY_MAPS_URL = "https://www.army.mil/asc#org-iowa-army-ammunition-plant"
# The Army's Nov. 24 "Mitigated 0.26" deposition and dispersion maps, linked from the Nov. 24
# advisory as the latest version (checked against the maintainer's copy of the PDF).
ARMY_MAPS_PDF = "https://d34w7g4gy10iej.cloudfront.net/pubs/pdf_78382.pdf"
ARMY_MAPS_CITE = "Army \u201cMitigated 0.26\u201d maps, Nov. 24"
# The blast itself. The New York Times live coverage of Nov. 25, 2026 reported the detonation
# as done; the maintainer read it there (this build's tools couldn't fetch nytimes.com, which
# blocks automated readers). Other outlets reported it too. No Army statement of the results
# had been checked when this was written, so the page says to wait for the Army's.
NYT_BLAST_URL = "https://www.nytimes.com/live/2026/11/25/us/iowa-detonation-ammunition-news"
NYT_BLAST_CITE = "New York Times, Nov. 25"
# The Army's last notice before the blast, "Today's controlled detonation at Iowa Army
# Ammunition Plant" (L. McFate, Army Sustainment Command, Nov. 25, 2026). Text checked from
# the maintainer's screenshot; army.mil refuses this build's tools (HTTP 403). It reads: "At
# 9:00 a.m. CST today, the U.S. Army will conduct a controlled, mitigated detonation ... the
# Army will update the public on the status of the operation no later than 11:00 a.m. CST."
ARMY_NOV25_URL = "https://www.army.mil/article/297089"
ARMY_NOV25_CITE = "Army update, Nov. 25"
# The Army's 3 p.m. update, "Deposition Maps as of 3:00 PM (CST) - Lead Azide" (army.mil
# article 297109, Nov. 25, 2026), two map slides stamped "a/o 251500NOV26", read from the
# images on api.army.mil. Air slide: "Sensors report no lead detection at this time", with a
# legend giving "0.18 ug/m3 - Lead Air Sampling Method Detection Limit". Ground slide: "Post
# detonation sampling underway. Results will be published when available." Its modeled
# "Mitigated 0.26" deposition areas: 27 sq mi above 100 ug/ft2, 191 sq mi above 5 ug/ft2.
# Both slides: "AWAIT US ARMY TO ANNOUNCE ALL-CLEAR DETERMINATION."
ARMY_3PM_URL = "https://www.army.mil/article/297109"
# CBS2 Iowa (Iowa's News Now), "Middletown officials say normal activities can resume
# following lead azide detonation," published Nov. 25, 2026, 7:28 p.m. CST; read in full on
# Nov. 25. Middletown City Clerk Brieanna Beck, in a Facebook post, said EPA air monitoring
# had detected no lead in surrounding areas and that the Army, CDC, EPA and FEMA had confirmed
# it was safe to resume normal activities. No Army all-clear statement had been posted on
# army.mil/asc when this was written, so the page attributes this to the city.
CBS2_RESUME_URL = (
    "https://cbs2iowa.com/news/local/"
    "middletown-officials-say-normal-activities-can-resume-following-lead-azide-detonation"
)
CBS2_RESUME_CITE = "CBS2 Iowa, Nov. 25"
# Airport observations at blast time (OBSERVED_WX).
IEM_URL = "https://mesonet.agron.iastate.edu/request/download.phtml?network=IA_ASOS"
IEM_CITE = "Iowa Environmental Mesonet, Nov. 25"
ARMY_3PM_CITE = "Army maps, Nov. 25, 3 p.m."
# EPA Region 7's public "Iowa Army Ammunition Plant Response Data Viewer" (ArcGIS), read on
# Nov. 25, 2026 at 4 p.m. CST from its public feature layers: four real-time (Xact) lead
# monitors, AS01-AS04, about 7 to 40 km southwest of the plant, reported 322 readings from
# 7:00 a.m. to 4:00 p.m. CST; the highest was 0.0102 ug/m3 (AS04, 10:00 a.m.), all below the
# Army's 0.18 ug/m3 detection limit (ARMY_3PM_URL). Its other 36 air stations (AS-05 to
# AS-40) collect samples for lab analysis, none posted yet.
EPA_VIEWER_URL = "https://experience.arcgis.com/experience/1ddcf8b9d8314971b00dac8893ae9cd6"
EPA_VIEWER_CITE = "EPA response data viewer, Nov. 25"
# What this site's analysis after the blast found (the page at ANALYSIS_PATH, built by
# brief_page.py from the brief's README; the numbers are in that brief's tables). Every
# place that reports it uses these words, with the caveat that it is unofficial.
ANALYSIS_HEAD = "EPA\u2019s monitors and the cloud\u2019s path."
ANALYSIS_QUESTION = "Were EPA\u2019s real-time lead monitors on the cloud\u2019s path?"
ANALYSIS = (
    "After the blast, this site checked where EPA\u2019s four real-time lead monitors sat. "
    "The forecasts, including the Army\u2019s, pointed the cloud to the southwest (toward "
    "about 230\u00b0), and the four monitors lined up along that path. Models rerun on "
    "NOAA\u2019s analysis of that morning\u2019s weather put the cloud farther south (toward "
    "about 215\u00b0). On that path, three of the monitors were outside the modeled cloud and "
    "the nearest was on its edge. So the near-zero readings can\u2019t show, by themselves, "
    "whether little lead got out or a cloud passed just south of the monitors. Lab results "
    "from EPA\u2019s filter samplers on the more southerly path, and from wipes of surfaces "
    "along it, can; soil samples probably can\u2019t, because the modeled amounts are far "
    "less than soil already holds. "
    "This is a preliminary, unofficial analysis of model estimates, not measurements, and no "
    "one outside the project has reviewed it."
)
ANALYSIS_TEXT = f"{ANALYSIS} The analysis: {ANALYSIS_URL}"
ANALYSIS_HTML = (
    html.escape(ANALYSIS, quote=False)
    + f' <a href="{ANALYSIS_PATH}">Read the preliminary analysis</a>.'
)
# Where readers find the agencies' own information: a line in the header of the landing
# page and of the analysis page.
OFFICIAL_HTML = (
    f'<b>Official information:</b> <a href="{EPA_VIEWER_URL}" rel="noopener">EPA&rsquo;s '
    "response data viewer</a> (air monitoring) &middot; "
    f'<a href="{ARMY_MAPS_URL}" rel="noopener">Army updates and maps</a> (army.mil/asc).'
)
EARLY_AIR = (
    "Every reading from EPA\u2019s four real-time lead monitors southwest of the plant, "
    "through 4 p.m. CST, was below the 0.18 micrograms per cubic meter detection limit the "
    f"Army cites ({EPA_VIEWER_CITE}). These are early readings only. Lab results from "
    "EPA\u2019s other air samples, and soil and water sampling, are still pending and are "
    "needed before anyone knows where lead settled."
)
# When the blast happened: the Army's 3 p.m. map slides (ARMY_3PM_URL) give the
# detonation's date-time group, "DTG: 25NOV2026 0900 CST". Consistent with Iowa Public Radio
# ("at approximately 9 a.m. Wednesday", read in full Nov. 25), the Army's post quoted by news
# live blogs ("At 9:00am CT, @USArmy Sustainment Command executed the controlled mitigated
# detonation"; not read first-hand), and Newsweek's report of two bangs at about 9:01 a.m.
# on a livestream about 5 miles away (sound takes about 25 seconds to travel that far).
BLAST_DONE = (
    "The Army carried out the controlled detonation at 9:00 a.m. CST on Wednesday, Nov. 25. "
    "In its 3 p.m. CST update, which gives that time, the Army said air sensors report no "
    "lead detection at this time, and that sampling of the ground after the detonation is "
    "underway, with results to be published when "
    f"available ({ARMY_3PM_CITE}). {EARLY_AIR} On Wednesday evening, Middletown\u2019s city "
    "clerk said the Army, CDC, EPA and FEMA had confirmed normal activities could resume "
    f"({CBS2_RESUME_CITE}). Follow official instructions."
)
BLAST_STATUS_HTML = (
    "<b>Blast done:</b> the Army carried out the detonation at 9:00 a.m. CST Wednesday, "
    "Nov. 25. At 3 p.m. CST the Army said air sensors report no lead detection at this time "
    "and ground sampling is underway "
    f'(<a href="{ARMY_3PM_URL}" rel="noopener">{ARMY_3PM_CITE}</a>). '
    "On Wednesday evening, Middletown&rsquo;s city clerk said the Army, CDC, EPA and FEMA had "
    "confirmed normal activities could resume "
    f'(<a href="{CBS2_RESUME_URL}" rel="noopener">{CBS2_RESUME_CITE}</a>). '
    "<b>Follow official instructions.</b>"
)
EARLY_AIR_HTML = (
    "<b>Early air readings:</b> every reading from EPA&rsquo;s four real-time lead monitors "
    "southwest of the plant, through 4 p.m. CST, was below the 0.18 &micro;g/m&sup3; "
    "detection limit the Army cites "
    f'(<a href="{EPA_VIEWER_URL}" rel="noopener">{EPA_VIEWER_CITE}</a>). These are early '
    "readings only: <b>lab results from EPA&rsquo;s other air samples, and soil and water "
    "sampling, are still pending and are needed</b> before anyone knows where lead settled. "
    f'A <a href="{ANALYSIS_PATH}">preliminary analysis</a> by this site finds those four '
    "monitors sat along the forecast path, and that models rerun on NOAA&rsquo;s weather "
    "analysis put the cloud south of them. Those are unofficial model estimates, not "
    "measurements."
)
# FEMA and the Army's advice, for the page header (Army public safety advisory, Nov. 24).
FEMA_HEADER_HTML = (
    "<b>FEMA evacuation (Nov. 24):</b> Middletown and a 5-mile cone southwest of the plant; "
    "outside it, the Army advised sheltering in place with windows and doors closed. FEMA Helpline "
    '<a href="tel:+18006213362">1-800-621-3362</a> (24/7) &middot; '
    '<a href="https://www.disasterassistance.gov/" rel="noopener">DisasterAssistance.gov</a>'
    f' &middot; <a href="{ADVISORY_NOV24_URL}" rel="noopener">Army advisory, Nov. 24</a>'
)
# FEMA's Wireless Emergency Alert ("Imminent Threat Alert") sent to phones near the plant on
# Nov. 24, 2026, with the same 9 a.m. time; text checked from the maintainer's screenshot. It
# has no public address, so it is named but not linked.
FEMA_CITE = "FEMA emergency alert, Nov. 24"
HHS_URL = "https://hhs.iowa.gov/media/19822/download?inline="
HHS_LINK = f'<a href="{HHS_URL}" rel="noopener">Iowa HHS fact sheet</a>'
# Sources named in parentheses without their address, as "(Iowa HHS fact sheet)". The page
# links each name (time_note_html, and make_map_picker.linkify for the FAQ).
NAMED_SOURCES = (
    (NYT_BLAST_CITE, NYT_BLAST_URL),
    (ARMY_NOV25_CITE, ARMY_NOV25_URL),
    (EPA_VIEWER_CITE, EPA_VIEWER_URL),
    (ARMY_3PM_CITE, ARMY_3PM_URL),
    (CBS2_RESUME_CITE, CBS2_RESUME_URL),
    (IEM_CITE, IEM_URL),
    (ADVISORY_NOV24_CITE, ADVISORY_NOV24_URL),
    ("Acting Secretary of the Army on X", SECARMY_URL),
    ("Iowa HHS fact sheet", HHS_URL),
    ("Nov. 22 court filing", RESPONSE_URL),
    (ARMY_MAPS_CITE, ARMY_MAPS_PDF),
    (BRIEFING_CITE, BRIEFING_URL),
)
# Far-reach distances swing a lot between forecast updates (see README "Why the numbers move").
REACH_NOTE = (
    "The farthest distances depend heavily on the evening forecast, especially how "
    "quickly the air near the ground calms at sunset, so these numbers can change a lot "
    "from one forecast update to the next."
)
CAVEAT = (
    "This is an unofficial estimate, not from the Army or any "
    "government agency. Follow official instructions."
)
ARMY_COMPARE = (
    "EPA\u2019s emergency permit requires the Army\u2019s official plume maps to assume that all "
    "of the lead gets into the air (an emission factor of 1.00). EPA calls this conservative "
    "and notes the Army expects the real release to be less. The \u201cEPA permit\u201d option "
    "here uses the same 100%. The Army\u2019s Nov. 24 \u201cMitigated 0.26\u201d maps use an "
    "emission factor of 0.26 for the blast with its barriers, foam and misters, and show 27 "
    "sq mi above 100 \u00b5g/ft\u00b2 and 148 sq mi above 5; the \u201cU.S. Army "
    "mitigated\u201d option here uses the same 26%. The permit also "
    "sets the Army\u2019s ground-lead map lines at 5 and 100 \u00b5g/ft\u00b2: inside 5, people "
    "are told to stay indoors; inside 100, also to wet-clean surfaces children touch. Those "
    "are the yellow and red levels here."
)
#: What NOAA and its HYSPLIT model are, for a reader who has heard of neither. The
#: description of HYSPLIT follows NOAA Air Resources Laboratory's own page (HYSPLIT_URL, read
#: Nov. 26, 2026): "one of the most extensively used atmospheric transport and dispersion
#: models", used for "radioactive material, wildfire smoke, windblown dust ... and volcanic
#: ash", and "used operationally by NOAA Weather Forecast Offices to plan for and respond to
#: emergency situations" (its About page).
HYSPLIT_URL = "https://www.arl.noaa.gov/hysplit/"
HYSPLIT_CITE = "NOAA Air Resources Laboratory"
HYSPLIT_HEAD = "How this compares with the NOAA HYSPLIT model"
HYSPLIT_QUESTION = "How does this compare with NOAA\u2019s HYSPLIT model?"
NOAA_WHAT = (
    "NOAA is the National Oceanic and Atmospheric Administration, the U.S. government\u2019s "
    "weather and ocean science agency. The National Weather Service is part of it."
)
HYSPLIT_WHAT = (
    "HYSPLIT is a computer model from NOAA\u2019s Air Resources Laboratory. It is told what "
    "was released, where, and when, and is given the winds from a weather model. It then "
    "works out where the air carries the material and how much comes down to the ground, by "
    "following a great many imaginary particles as the wind moves and spreads them. NOAA "
    "calls it one of the most widely used models of its kind. It is used to track wildfire "
    "smoke, volcanic ash, windblown dust, and releases of radioactive material, and "
    f"NOAA\u2019s weather offices use it in emergencies ({HYSPLIT_CITE})."
)
HYSPLIT_HOW = (
    "NOAA did not run it for this blast. This site ran NOAA\u2019s public copy of HYSPLIT "
    "itself, for the same assumed release, on NOAA\u2019s own archive of that morning\u2019s "
    "weather. The \u201cNOAA HYSPLIT\u201d button under the map shows the result. It is a second "
    "estimate, from a different kind of model than this site\u2019s. It is not a measurement, "
    "and it is not a forecast from NOAA."
)
HYSPLIT_LIMIT = (
    "HYSPLIT\u2019s result has a grainy edge, because it follows particles, so its distances "
    "here are good to a mile or two; stray specks past the main area are left out. Two models "
    "agreeing does not show that either is right. Both were given the same guess about how "
    "much lead got into the air, and both ran on the same NOAA weather model."
)
HYSPLIT_TABLE_HEAD = (
    '<thead><tr><th scope="col">Case (share of lead airborne)</th>'
    '<th scope="col">This site\u2019s model</th>'
    '<th scope="col">NOAA HYSPLIT, run by this site</th></tr></thead>'
)
CASE_WORD = {"permit": "EPA permit", "high": "high", "mid": "U.S. Army mitigated", "low": "low"}
SAFETY_ANSWER = (
    "Don't use this map to decide if you're safe. Follow instructions from the Army, your "
    "county emergency management office, and state health officials."
)
DEP_TABLE_HEAD = (
    '<thead><tr><th scope="col">Case (share of lead airborne)</th>'
    '<th scope="col">Yellow, 5 \u00b5g/ft\u00b2</th>\n'
    '      <th scope="col">Orange, 40 \u00b5g/ft\u00b2</th>'
    '<th scope="col">Red, 100 \u00b5g/ft\u00b2</th></tr></thead>'
)
SOURCES = [
    f"- Army postponement: {ARMY_URL}",
    (
        "- EPA emergency permit (emission factor 1.00; 5 and 100 \u00b5g/ft\u00b2 notification "
        f"lines): {PERMIT_URL}"
    ),
    (
        "- Amount, 9,700 lb in 68 barrels (Army spokesperson): "
        "https://abcnews.com/US/iowa-army-plant-lead-azide-detonation/story?id=138261613"
    ),
    f"- Two detonations Monday at approximately noon: Iowa HHS fact sheet for Nov. 23, {HHS_URL}",
    (
        "- EPA dust-lead action levels, 40 CFR 745.227: "
        "https://www.ecfr.gov/current/title-40/part-745/section-745.227"
    ),
    "- DOE Protective Action Criteria (PAC/TEEL): https://emhub1.energy.gov/pacteel",
    (
        "- EPA AP-42 Chapter 15, ordnance detonation: "
        "https://www.epa.gov/air-emissions-factors-and-quantification/"
        "ap-42-fifth-edition-volume-i-chapter-15-ordnance"
    ),
    "- Weather forecasts: Open-Meteo (https://open-meteo.com)",
]


# ---------------------------------------------------------------------------
# Reading the maps


def load_map(path: str | Path) -> dict[str, Any]:
    """Return the model payload embedded in a built map page."""
    s = Path(path).read_text(encoding="utf-8")
    i = s.index("const DATA = ") + len("const DATA = ")
    data: dict[str, Any] = json.JSONDecoder().raw_decode(s[i:])[0]
    return data


def field(d: dict[str, Any], name: str) -> FloatArray:
    """Decode a packed field to an array (hours, ny, nx) in its own units; 0 = below range."""
    g, p = d["grid"], d["grid"][name]
    raw = np.frombuffer(zlib.decompress(base64.b64decode(p["data"])), np.uint8)
    q = raw.reshape(-1, g["ny"], g["nx"]).astype(float)
    v = 10 ** (p["lo"] + (q - 1) / 254 * (p["hi"] - p["lo"]))
    return np.where(q > 0, v, 0.0)


def dist_bearing(lat0: float, lon0: float, lat: float, lon: float) -> tuple[float, float]:
    """Return distance (km) and bearing (degrees from north) on a local flat-Earth grid."""
    dy = (lat - lat0) * KM_PER_DEG_LAT
    dx = (lon - lon0) * KM_PER_DEG_LAT * math.cos(math.radians(lat0))
    return math.hypot(dx, dy), (math.degrees(math.atan2(dx, dy)) + 360) % 360


def compass(b: float) -> str:
    """Return the 16-point compass name (N, NNE, ...) for a bearing in degrees."""
    return COMPASS[round(b / 22.5) % 16]


def cell_of(g: dict[str, Any], lat: float, lon: float) -> tuple[int, int] | None:
    """Return the (row, column) of the grid cell holding a point, or None if off the grid."""
    i = int((lon - g["west"]) / (g["east"] - g["west"]) * g["nx"])
    j = int((g["north"] - lat) / (g["north"] - g["south"]) * g["ny"])
    return (j, i) if 0 <= i < g["nx"] and 0 <= j < g["ny"] else None


def zone_stats(d: dict[str, Any], arr2d: FloatArray, threshold: float) -> tuple[float, float]:
    """Return (farthest distance km, area km2) of cells at or above threshold."""
    g, m = d["grid"], d["meta"]
    js, is_ = np.nonzero(arr2d >= threshold)
    if not len(js):
        return 0.0, 0.0
    lat = g["north"] - (js + 0.5) / g["ny"] * (g["north"] - g["south"])
    lon = g["west"] + (is_ + 0.5) / g["nx"] * (g["east"] - g["west"])
    dy = (lat - m["lat"]) * KM_PER_DEG_LAT
    dx = (lon - m["lon"]) * KM_PER_DEG_LAT * math.cos(math.radians(m["lat"]))
    return float(np.hypot(dx, dy).max()), len(js) * (g["dx"] / 1000) ** 2


def joined_to_peak(arr2d: FloatArray, threshold: float) -> FloatArray:
    """Return ``arr2d`` with zeros outside the area at or above ``threshold`` around its peak.

    Keeps the cells joined edge to edge to the highest cell. A model that follows particles
    (HYSPLIT) leaves stray cells past the edge of its result; measuring a farthest distance
    on them would follow the grain, not the cloud.
    """
    at = arr2d >= threshold
    keep = np.zeros(at.shape, dtype=bool)
    start = np.unravel_index(int(np.argmax(arr2d)), arr2d.shape)
    if not at[start]:
        return np.zeros_like(arr2d)
    stack = [(int(start[0]), int(start[1]))]
    keep[start] = True
    while stack:
        j, i = stack.pop()
        for y, x in ((j - 1, i), (j + 1, i), (j, i - 1), (j, i + 1)):
            if 0 <= y < at.shape[0] and 0 <= x < at.shape[1] and at[y, x] and not keep[y, x]:
                keep[y, x] = True
                stack.append((y, x))
    return np.where(keep, arr2d, 0.0)


def center_bearing(d: dict[str, Any], arr2d: FloatArray) -> float | None:
    """Return the bearing from the source to the middle (center of mass) of a field."""
    g, m = d["grid"], d["meta"]
    total = float(arr2d.sum())
    if total <= 0:
        return None
    lat = g["north"] - (np.arange(g["ny"]) + 0.5) / g["ny"] * (g["north"] - g["south"])
    lon = g["west"] + (np.arange(g["nx"]) + 0.5) / g["nx"] * (g["east"] - g["west"])
    la = float((arr2d.sum(axis=1) * lat).sum()) / total
    lo = float((arr2d.sum(axis=0) * lon).sum()) / total
    return dist_bearing(m["lat"], m["lon"], la, lo)[1]


def towns_at_or_above(d: dict[str, Any], arr2d: FloatArray, threshold: float) -> list[str]:
    """Return the listed towns whose grid cell is at or above threshold."""
    out = []
    for name, la, lo in TOWNS:
        c = cell_of(d["grid"], la, lo)
        if c and arr2d[c] >= threshold:
            out.append(name)
    return out


def local_clock(iso: str, off_min: int) -> str:
    """Return a UTC ISO time as a local clock time such as '1:00 p.m.'."""
    t = dt.datetime.fromisoformat(iso.replace("Z", "+00:00")) + dt.timedelta(minutes=off_min)
    h = t.hour % 12 or 12
    return f"{h}:{t.minute:02d} {'a.m.' if t.hour < NOON[0] else 'p.m.'}"


# ---------------------------------------------------------------------------
# Facts


def _blast_words(default_time: str) -> str:
    h_, m_ = map(int, default_time.split(":"))
    if (h_, m_) == NOON:
        return "noon"
    return f"{(h_ - 1) % 12 + 1}:{m_:02d} {'a.m.' if h_ < NOON[0] else 'p.m.'}"


def _new_case(label: str) -> dict[str, Any]:
    return {
        "label": label,
        "dep": {k: [0.0, 0.0] for k in DEP_COLORS},
        "dep_env": dict.fromkeys(DEP_COLORS, 0.0),  # farthest across all forecasts
        "towns": {k: set() for k in DEP_COLORS},
        "air_max": 0.0,
        "pac1_km": 0.0,
        "pac1_env_km": 0.0,
        "lead_lb": None,
        "share": None,
        # where the lead on the ground lies, and NOAA HYSPLIT's result where the map has one
        "dep_bearing": None,
        "hy_dep": None,
        "hy_bearing": None,
    }


def _add_map_to_case(c: dict[str, Any], d: dict[str, Any], out: Facts) -> None:
    """Fold one map (one blast time) into a case's running maxima."""
    m = d["meta"]
    c["lead_lb"] = m["releaseMass"] / KG_PER_LB
    out["azide_lb"] = m["explosion"]["mass"] / KG_PER_LB
    out["lead_total_lb"] = out["azide_lb"] * m["trackedFraction"]
    c["share"] = m["explosionOpts"]["airborneFraction"]
    dep_end = field(d, "dep")[-1]
    for k, ugft2 in DEP_LEVELS:
        km, area = zone_stats(d, dep_end, ugft2 * KG_M2_PER_UG_FT2)
        c["dep"][k][0] = max(c["dep"][k][0], km)
        c["dep"][k][1] = max(c["dep"][k][1], area)
        c["towns"][k].update(towns_at_or_above(d, dep_end, ugft2 * KG_M2_PER_UG_FT2))
    c["dep_bearing"] = center_bearing(d, dep_end)
    if "hy_dep" in d["grid"]:  # the saved NOAA HYSPLIT run, on this map's grid and case
        hy_end = field(d, "hy_dep")[-1]
        c["hy_dep"] = {}
        for k, ugft2 in DEP_LEVELS:  # without the stray cells past its grainy edge
            level = ugft2 * KG_M2_PER_UG_FT2
            c["hy_dep"][k] = zone_stats(d, joined_to_peak(hy_end, level), level)[0]
        c["hy_bearing"] = center_bearing(d, hy_end)
    if "env_dep" in d["grid"]:
        env_end = field(d, "env_dep")[-1]
        for k, ugft2 in DEP_LEVELS:
            km = zone_stats(d, env_end, ugft2 * KG_M2_PER_UG_FT2)[0]
            c["dep_env"][k] = max(c["dep_env"][k], km)
    m60 = field(d, "m60").max(axis=0)
    c["air_max"] = max(c["air_max"], float(np.max(m60)) * 1e9)
    c["pac1_km"] = max(c["pac1_km"], zone_stats(d, m60, PAC1_KG_M3)[0])
    if "env_m60" in d["grid"]:
        env_m60 = field(d, "env_m60").max(axis=0)
        c["pac1_env_km"] = max(c["pac1_env_km"], zone_stats(d, env_m60, PAC1_KG_M3)[0])


def _shown_map_facts(d: dict[str, Any], out: Facts) -> None:
    """Record the winds, permit weather and cloud path from the map shown by default."""
    m = d["meta"]
    out["shown_model"] = (m.get("ensemble") or {}).get("shown")
    h0 = d["hours"][0]
    out["winds"] = (h0["ws"], h0["wd"])
    # EPA permit weather limits, checked for the first hour after the blast
    lo_m, hi_m = PERMIT_ALOFT_M
    aloft = [q[1] for q in h0.get("prof", []) if lo_m <= q[0] <= hi_m]
    out["permit_wx"] = {
        "sfc_mph": h0["ws"] * MPH_PER_M_S,
        "aloft_mph": max(aloft) * MPH_PER_M_S if aloft else None,
        "precip": h0["precip"],
        "cloud": h0["cloud"],
        "stab": h0["stab"],
    }
    for h in d["hours"]:
        if not h.get("centroid"):
            continue
        la, lo = h["centroid"]
        km, b = dist_bearing(m["lat"], m["lon"], la, lo)
        near = min((dist_bearing(la, lo, tla, tlo)[0], n) for n, tla, tlo in TOWNS)
        out["path"].append(
            {
                "clock": local_clock(h["t"], m["tzOffsetMin"]),
                "km": km,
                "dir": compass(b),
                "near": near[1] if near[0] <= NEAR_TOWN_KM else None,
            }
        )


def facts(
    maps: dict[tuple[str, str], str | Path],
    cases: list[tuple[str, str, str]],
    times: list[str],
    default_time: str,
) -> Facts:
    """Read every map and return the numbers and short strings the text is built from.

    Parameters
    ----------
    maps
        Map page for each (case id, blast time).
    cases
        (case id, release case, label) for each case, in display order.
    times
        Blast times ("11:00", ...).
    default_time
        Blast time shown by default; the wind and path facts come from its middle case.
    """
    out: Facts = {
        "blast": _blast_words(default_time),
        "cases": {},
        "path": [],
        "winds": None,
        "shown_model": None,
        "lead_total_lb": None,
        "azide_lb": None,
        "permit_wx": None,
    }
    for case, _, label in cases:
        c = _new_case(label)
        for t in times:
            d = load_map(maps[(case, t)])
            _add_map_to_case(c, d, out)
            if case == "mid" and t == default_time:
                _shown_map_facts(d, out)
        c["towns"] = {k: sorted(v, key=TOWN_ORDER.__getitem__) for k, v in c["towns"].items()}
        out["cases"][case] = c
    return out


# ---------------------------------------------------------------------------
# Wording


TIME_HEAD = "When."
# Subheading for the dates the Army planned before the current one, newest first.
EARLIER_HEAD = "Earlier dates."


def _time_parts(built_txt: str) -> dict[str, str]:
    """Return the time paragraph's sentences by topic: when, evacuation, maps, window."""
    return {
        "when": (f"As of this update ({built_txt}), {BLAST_DONE[0].lower()}{BLAST_DONE[1:]}"),
        "evacuation": (
            "Before the blast, FEMA supported relocating all residents of Middletown and the "
            "immediate surrounding areas, starting Nov. 24; the evacuation zone was a 5-mile cone"
            " extending southwest of the plant, reaching one mile beyond the Army\u2019s modeled "
            "dispersion path. The Army encouraged people outside the zone to shelter in place, "
            "closing all windows and doors (Army public safety advisory, Nov. 24). Questions "
            "about the evacuation area or help: FEMA Helpline 1-800-621-3362 (24/7) or "
            "DisasterAssistance.gov."
        ),
        "maps": (
            "The Army\u2019s latest maps still show its model estimate for the mitigated "
            "blast, using an emission factor of 0.26: lead on surfaces above 100 \u00b5g/ft\u00b2 "
            "over 27 square miles and above 5 \u00b5g/ft\u00b2 over 191 square miles; ground "
            f"sampling is underway to check it ({ARMY_3PM_CITE}). Its earlier maps used the "
            f"same 0.26 ({ARMY_MAPS_CITE}). The Army\u2019s maps and updates are at "
            f"{ARMY_MAPS_URL}."
        ),
        "window": (f"These maps model a blast at {BLAST_TIME}, the time the Army had set."),
    }


def time_note(built_txt: str) -> str:
    """Give the key facts first: the time, the official evacuation and shelter advice, the maps.

    The timeline that led here (court case, presidential hold, earlier dates) comes after it
    on the page, under its own headings.
    """
    p = _time_parts(built_txt)
    return " ".join(p[k] for k in ("when", "evacuation", "maps", "window"))


def _link_sources(text: str) -> str:
    """Link the named sources, army.mil/asc and DisasterAssistance.gov in ``text``."""
    out = text
    for name, url in NAMED_SOURCES:
        out = out.replace(f"({name})", f'(<a href="{url}" rel="noopener">{name}</a>)')
    return out.replace(
        ARMY_MAPS_URL, f'<a href="{ARMY_MAPS_URL}" rel="noopener">army.mil/asc</a>'
    ).replace(
        "DisasterAssistance.gov",
        '<a href="https://www.disasterassistance.gov/" rel="noopener">DisasterAssistance.gov</a>',
    )


def time_note_html(built_txt: str) -> str:
    """Return time_note() with its sources linked."""
    return _link_sources(time_note(built_txt))


#: The About box's first three headings (its short form of the time paragraph).
EVACUATION_HEAD = "Evacuation and help."
ARMY_MAPS_HEAD = "The Army\u2019s maps."


def about_time_html(built_txt: str) -> str:
    """Return time_note()'s sentences as three short About-box paragraphs, linked.

    When (with the FEMA alert and the times modeled), then the evacuation zone and helpline,
    then the Army's own maps, so a reader on a phone finds the official help at a glance.
    """
    p = {k: _link_sources(v) for k, v in _time_parts(built_txt).items()}
    return (
        f"<p><b>{TIME_HEAD}</b> {p['when']} {p['window']}</p>\n"
        f"  <p><b>{EVACUATION_HEAD}</b> {p['evacuation']}</p>\n"
        f"  <p><b>{ARMY_MAPS_HEAD}</b> {p['maps']}</p>"
    )


def lb(x: float) -> str:
    """Round pounds the way people say them: 480, 1,380, 6,900."""
    return f"{round(x, -1 if x < 1000 else -2):,.0f}"


def mi(km: float) -> str:
    """Return a distance in miles, with one decimal under 10."""
    return f"{km / MI:.0f}" if km / MI >= 10 else f"{km / MI:.1f}"


def kmf(km: float) -> str:
    """Return a distance in kilometers, with one decimal under 10."""
    return f"{km:.0f}" if km >= 10 else f"{km:.1f}"


def both(km: float, *, html: bool = True) -> str:
    """Return '12 miles (19 km)' in text, or unit-switching spans in HTML."""
    if not html:
        return f"{mi(km)} miles ({kmf(km)} km)"
    return (
        f'<span class="u-us">{mi(km)} miles</span><span class="u-metric" hidden>{kmf(km)} km</span>'
    )


def join(names: list[str]) -> str:
    """Join town names with semicolons, since each has a comma: 'Wever, Iowa; and X'."""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:  # "Middletown, Iowa, and Fort Madison, Iowa" (comma after the state)
        return names[0] + (", and " if "," in names[0] else " and ") + names[1]
    return "; ".join(names[:-1]) + "; and " + names[-1]


def dot(text: str) -> str:
    """End a sentence without doubling an abbreviation's period ('Mo.')."""
    return text if text.endswith(".") else text + "."


def path_sentence(f: Facts, *, html: bool = True) -> str:
    """Describe where the center of the cloud goes and when."""
    p = f["path"]
    if not p:
        return "The cloud stays near the plant."
    end, seen, names = p[-1], set(), []
    for x in p:
        if x["near"] and x["near"] not in seen:
            seen.add(x["near"])
            names.append(x["near"])
    first = p[0]
    via = f", passing near {join(names)}" if names else ""
    first_dir = WORDS[first["dir"]]
    return (
        dot(
            f"For a {f['blast']} blast, the center of the model\u2019s cloud moves {first_dir}{via}"
        )
        + f" By {first['clock']} it is about {both(first['km'], html=html)} {first_dir} of the "
        f"plant, and by {end['clock']} about {both(end['km'], html=html)} {WORDS[end['dir']]}."
    )


def wind_sentence(f: Facts) -> str:
    """Describe the surface wind at blast time and where it carries the cloud."""
    if not f["winds"]:
        return ""
    ws, wd = f["winds"]
    return (
        f"Winds near the ground at blast time were forecast from the {WORDS[compass(wd)]} at "
        f"about {ws * MPH_PER_M_S:.0f} mph ({ws:.1f} m/s), which carries the model\u2019s cloud "
        f"{WORDS[compass((wd + 180) % 360)]}."
    )


def _case_rows(f: Facts, ctx: dict[str, Any], model_short: str) -> tuple[list[str], list[str]]:
    """Return the ground-lead table rows as HTML and as text lines."""
    c, pct = f["cases"], ctx["pct"]
    rows_html, rows_txt = [], []
    for case in _order(f):
        x = c[case]
        cells = [
            both(x["dep"][k][0])
            + (
                f"<br><small>up to {both(x['dep_env'][k])} in any forecast</small>"
                if x["dep_env"][k] > x["dep"][k][0] * SPREAD_SHOWN
                else ""
            )
            for k in DEP_COLORS
        ]
        rows_html.append(
            f'<tr><th scope="row">{x["label"]} ({pct[case]}, about '
            f"{lb(x['lead_lb'])} lb of lead)</th>"
            + "".join(f"<td>{v}</td>" for v in cells)
            + "</tr>"
        )
        rows_txt.append(
            f"- {x['label']} ({pct[case]} of the lead airborne, about {lb(x['lead_lb'])} lb): "
            + ", ".join(
                f"{k} up to {both(x['dep'][k][0], html=False)} with {model_short} "
                f"({both(x['dep_env'][k], html=False)} in any forecast)"
                for k in DEP_COLORS
            )
            + "."
        )
    return rows_html, rows_txt


def _order(f: Facts) -> list[str]:
    return [k for k in ("low", "mid", "high", "permit") if k in f["cases"]]


def _town_text(f: Facts) -> str:
    """Say which listed towns fall in the yellow area, case by case."""
    c = f["cases"]
    # Lead with the most conservative case, then the smaller ones.
    lead = "permit" if "permit" in c else "high"
    first = c[lead]["towns"]["yellow"]
    opening = f"In the {CASE_WORD[lead]} case (the largest of the four), "
    town_txt = dot(
        opening + f"the model\u2019s yellow area reaches {join(first)}"
        if first
        else opening + "no listed town is in the model\u2019s yellow area"
    )
    prev = first
    for k in ("high", "mid", "low"):  # each smaller case in its own sentence
        if k in c and k != lead:
            tw = c[k]["towns"]["yellow"]
            if tw and tw == prev:
                what = "the same towns"
            else:
                what = join(tw) if tw else "none of the listed towns"
            town_txt += " " + dot(f"The {CASE_WORD[k]} case reaches {what}")
            prev = tw
    return town_txt


def _air_text(f: Facts, model: str, n_models: str, *, html: bool) -> str:
    """Describe the highest one-hour air lead and how far it stays above DOE PAC-1."""
    c, order = f["cases"], _order(f)
    names = [CASE_WORD.get(k, c[k]["label"].lower()) for k in order]
    names_txt = ", ".join(names[:-1]) + ", and " + names[-1]
    *rest, last = order

    def listed(key: str) -> str:
        return ", ".join(both(c[k][key], html=html) for k in rest) + (
            f", and {both(c[last][key], html=html)}"
        )

    return (
        "The highest one-hour average of lead in the air is about "
        + ", ".join(f"{c[k]['air_max']:,.0f}" for k in rest)
        + f", and {c[last]['air_max']:,.0f}"
        + f" \u00b5g/m\u00b3 for the {names_txt} cases, all close to the plant. DOE\u2019s PAC-1 "
        "level for lead, for a one-hour exposure, is 32 \u00b5g/m\u00b3. The model has the "
        "one-hour average above it out to about "
        + listed("pac1_km")
        + f" with the {model or 'main'} forecast. Across all {n_models} forecasts, with "
        "either of two dry-deposition schemes, it reaches "
        "up to " + listed("pac1_env_km") + "."
    )


def _permit_weather_text(f: Facts) -> str:
    """Compare the blast-time forecast with the permit's weather limits."""
    w = f["permit_wx"] or {}
    if not w:
        return ""
    lo, hi = PERMIT_SFC_MPH
    ok = lo <= w["sfc_mph"] <= hi and (w["aloft_mph"] or 0) <= PERMIT_ALOFT_MPH and w["precip"] == 0
    aloft = f", up to {w['aloft_mph']:.0f} mph at 1,000 to 3,000 feet" if w["aloft_mph"] else ""
    return (
        "The permit bars the blast with surface winds under 1 or over 15 mph, winds over 30 mph "
        "at 1,000 to 3,000 feet, rain, thunderstorms, fog, a low overcast, or an inversion. "
        f"For {f['blast']} {f.get('day', PLANNED_DAY).split(',')[0]} the forecast had surface "
        f"winds of about {w['sfc_mph']:.0f} mph"
        + aloft
        + f", {w['cloud']:.0f}% cloud cover, and {'no rain' if not w['precip'] else 'rain'}, "
        + ("which is inside those limits." if ok else "which is outside at least one of them.")
        + (
            f" {OBSERVED_SKY}"
            if f["blast"].startswith("9:00") and f.get("day", PLANNED_DAY) == PLANNED_DAY
            else ""
        )
    )


#: Where the archived weather comes from, for every place that names it.
ARCHIVED_SOURCE = (
    "NOAA\u2019s HRRR weather model as Open-Meteo served it at 6:51 p.m. CST on Nov. 25, "
    "after the eight hours the maps cover had passed"
)
DEFAULT_VIEW_HEAD = "What the map opens on"
DEFAULT_VIEW_QUESTION = "What does the map show when it opens?"
ARCHIVED_HEAD = "With archived weather"
#: The button under the archived-weather maps that switches to NOAA's HYSPLIT result.
HYSPLIT_BOX = (
    "On these maps, the \u201cNOAA HYSPLIT\u201d button under the map switches to a second "
    "opinion: the result of NOAA\u2019s HYSPLIT model for the same assumed release, run on "
    "NOAA\u2019s own archive of the same weather model. It is drawn in the four colors of "
    "HYSPLIT\u2019s own plots, between the same lowest and highest levels as this "
    "site\u2019s map. It is another model\u2019s estimate, not a measurement, and not a "
    "forecast from NOAA."
)
#: The box under the blast's maps that draws the zones of the Army's own final maps.
ARMY_BOX = (
    "Under the map, the \u201cArmy\u2019s final forecast\u201d box draws the zones from the "
    "Army\u2019s own final maps over either model\u2019s result: where the Army\u2019s "
    "forecast put lead in air at 0.18 micrograms per cubic meter or more, with the times it "
    "marked along the path, and lead on the ground at 5 and 100 micrograms per square foot "
    "or more. The Army\u2019s maps are a forecast for 26% of the lead airborne, whichever "
    "case this map shows. This site traced the zones from the Army\u2019s pictures and placed "
    "them by their county lines, to about 0.6 mile (1 km); the Army\u2019s plant marker hides "
    "about their first 8 miles (13 km)."
)
#: Where the Army posted its final maps (DVIDS, Nov. 25, 2026; the pages were read Nov. 26).
ARMY_AIR_MAP_URL = "https://www.dvidshub.net/image/10118629/deposition-map-2-800-am-cst"
ARMY_GROUND_MAP_URL = "https://www.dvidshub.net/image/10118630/deposition-map-1-800-am-cst"
ARMY_BOX_LINKS = f"The Army\u2019s maps: air, {ARMY_AIR_MAP_URL}; ground, {ARMY_GROUND_MAP_URL}."
ARMY_BOX_LINKS_HTML = (
    f'The Army&rsquo;s maps: <a href="{ARMY_AIR_MAP_URL}" rel="noopener">air</a> and '
    f'<a href="{ARMY_GROUND_MAP_URL}" rel="noopener">ground</a> (DVIDS).'
)
FORECAST_HEAD = "What the forecast showed before the blast"
FORECAST_NOTE = (
    "The sections below on where the cloud goes, how far lead on the ground could reach, lead "
    "in the air, and the Army\u2019s maps describe the forecast maps: choose "
    "\u201cForecast (before the blast)\u201d in the Weather menu to see them."
)
#: Starts the two answers that describe the forecast maps once the page opens on archived
#: weather.
FORECAST_PREFIX = "With the forecast from before the blast: "


def default_view(pct_low: str) -> str:
    """Say what the page shows when it opens, and that this is not a finding."""
    return (
        f"The map opens on a blast at {BLAST_TIME}, the low case ({pct_low} of the lead in "
        f"the air), and archived weather: {ARCHIVED_SOURCE}. The Weather menu also has the "
        "forecast the site showed before the blast, and the \u201cLead in the air\u201d menu "
        "has the three larger cases, up to the EPA permit case, which assumes all of the lead "
        "got into the air. Opening on the low case is not a finding that little lead got "
        "out: no one has published how much did. Archived weather is a weather model\u2019s "
        "account of the day, not a measurement of where the cloud went."
    )


def about_weather(n_models: str, got_txt: str, *, archived: bool) -> str:
    """Say in the About box which weather the maps use."""
    forecast = f"{n_models} weather forecasts, current as of {got_txt}"
    if not archived:
        return f"The winds come from {forecast}."
    return (
        "The map opens on the low case, the smallest of the four; that is not a finding "
        "that little lead got out. It opens on archived weather: "
        f"{ARCHIVED_SOURCE}. The Weather menu also has "
        f"the forecast shown before the blast, from {forecast}. Archived weather is a weather "
        "model\u2019s account of the day, not a measurement."
    )


def weather_line(got_txt: str, *, archived: bool) -> str:
    """Say in the header which weather the maps use."""
    if not archived:
        return f"Weather forecast from {got_txt}."
    return (
        "Weather: archived (NOAA HRRR, saved Nov. 25, 6:51 p.m. CST), or the forecast from "
        f"{got_txt}."
    )


# Airport weather at blast time, from the Iowa Environmental Mesonet's ASOS archive (read
# Nov. 26, 2026 for 8:30-10:30 a.m. CST Nov. 25): Burlington (BRL, about 8 miles
# east-southeast of the plant) 8:53 a.m., wind 50 deg at 8 kt, clear; Fort Madison (FSW,
# about 12 miles south-southwest) 8:55 and 9:15 a.m., 10 deg at 8-10 kt, clear; Mount
# Pleasant (MPZ, about 15 miles west-northwest) 8:55 and 9:15 a.m., 40-50 deg at 6-7 kt,
# clear. ASOS ceilometers report clouds only up to 12,000 feet.
OBSERVED_WX = (
    "Weather observed at blast time: Burlington\u2019s airport, about 8 miles east-southeast "
    "of the plant, reported wind from the northeast at about 9 mph and clear skies at "
    "8:53 a.m., and the Fort Madison and Mount Pleasant airports reported north to northeast "
    f"winds of about 7 to 12 mph and clear skies ({IEM_CITE}). The archived and forecast "
    "winds are close to that."
)
OBSERVED_SKY = (
    "Airports near the plant reported clear skies at blast time, though their sensors see "
    f"clouds only up to 12,000 feet ({IEM_CITE})."
)


def archived_wind_sentence(f: Facts) -> str:
    """Describe the surface wind at blast time in the archived weather."""
    if not f["winds"]:
        return ""
    ws, wd = f["winds"]
    return (
        f"In the archived weather, winds near the ground at blast time were from the "
        f"{WORDS[compass(wd)]} at about {ws * MPH_PER_M_S:.0f} mph ({ws:.1f} m/s), which carries "
        f"the model\u2019s cloud {WORDS[compass((wd + 180) % 360)]}."
    )


def _archived_rows(f: Facts, pct: dict[str, str]) -> tuple[list[str], list[str]]:
    """Return the archived-weather ground-lead rows as HTML and as text lines.

    These maps have one weather source, so the smaller number is the farther of the two
    dry-deposition schemes, not the farthest forecast.
    """
    c = f["cases"]
    rows_html, rows_txt = [], []
    for case in _order(f):
        x = c[case]
        more = {k: x["dep_env"][k] > x["dep"][k][0] * SPREAD_SHOWN for k in DEP_COLORS}
        cells = [
            both(x["dep"][k][0])
            + (
                f"<br><small>up to {both(x['dep_env'][k])} with the other deposition scheme</small>"
                if more[k]
                else ""
            )
            for k in DEP_COLORS
        ]
        rows_html.append(
            f'<tr><th scope="row">{x["label"]} ({pct[case]}, about '
            f"{lb(x['lead_lb'])} lb of lead)</th>"
            + "".join(f"<td>{v}</td>" for v in cells)
            + "</tr>"
        )
        rows_txt.append(
            f"- {x['label']} ({pct[case]} of the lead airborne, about {lb(x['lead_lb'])} lb): "
            + ", ".join(
                f"{k} up to {both(x['dep'][k][0], html=False)}"
                + (
                    f" ({both(x['dep_env'][k], html=False)} with the other deposition scheme)"
                    if more[k]
                    else ""
                )
                for k in DEP_COLORS
            )
            + "."
        )
    return rows_html, rows_txt


def _archived_html(fa: Facts | None, pct: dict[str, str]) -> str:
    """Return the summary's sections on the default view and the archived-weather maps."""
    if not fa:
        return ""
    rows, _ = _archived_rows(fa, pct)
    return f"""<h3>{DEFAULT_VIEW_HEAD}</h3>
  <p>{default_view(pct["low"])}</p>
  <h3>{ARCHIVED_HEAD}</h3>
  <p>{archived_wind_sentence(fa)} {path_sentence(fa)} {OBSERVED_WX}</p>
  <p>{HYSPLIT_BOX}</p>
  <p>{ARMY_BOX} {ARMY_BOX_LINKS_HTML}</p>
  <p>Farthest distance from the plant where lead on the ground reaches each EPA dust-lead
    action level by the end of the 8-hour run, for a blast at {BLAST_TIME} The smaller
    number, where there is one, is the farther of the two dry-deposition schemes.</p>
  <div class="tablewrap"><table>
    {DEP_TABLE_HEAD}
    <tbody>{"".join(rows)}</tbody></table></div>
  <p>{_town_text(fa)} Town checks use approximate town centers. {TOWN_CAVEAT}</p>
  <h3>{FORECAST_HEAD}</h3>
  <p>{FORECAST_NOTE}</p>
  """


def _archived_plain(fa: Facts, pct: dict[str, str]) -> str:
    """Return the default view and the archived-weather facts as one plain paragraph."""
    _, rows = _archived_rows(fa, pct)
    return (
        f"{default_view(pct['low'])} {archived_wind_sentence(fa)} "
        f"{path_sentence(fa, html=False)} {OBSERVED_WX} {_town_text(fa)} {TOWN_CAVEAT} "
        "Farthest reach of ground lead with archived weather: "
        + " ".join(r[2:] for r in rows)
        + f" {HYSPLIT_BOX} {ARMY_BOX} {ARMY_BOX_LINKS}"
    )


SAME_LINE_DEG = 10  # bearings this close are "nearly the same line"


def _hysplit_result(fa: Facts, pct: dict[str, str], *, html: bool) -> tuple[str, list[str], str]:
    """Return the comparison sentences, a row for each case, and which model reaches farther."""
    c = fa["cases"]
    first = c[_order(fa)[0]]
    ours, theirs = first["dep_bearing"], first["hy_bearing"]
    same = abs(ours - theirs) <= SAME_LINE_DEG
    along = "nearly the same line" if same else "different lines"
    line = (
        f"Both models put the lead on the ground along {along} from the plant, toward the "
        f"{WORDS[compass(ours)]}: {ours:.0f}\u00b0 for this site\u2019s model and "
        f"{theirs:.0f}\u00b0 for HYSPLIT, measured to the middle of the lead on the ground. "
        "They differ more on how far it reaches. Farthest distance from the plant where lead "
        "on the ground reaches 5 \u00b5g/ft\u00b2 by the end of the 8 hours:"
    )
    rows = []
    for case in _order(fa):
        x = c[case]
        mine = both(x["dep"]["yellow"][0], html=html)
        noaa = both(x["hy_dep"]["yellow"], html=html)
        if html:
            rows.append(
                f'<tr><th scope="row">{x["label"]} ({pct[case]})</th>'
                f"<td>{mine}</td><td>{noaa}</td></tr>"
            )
        else:
            rows.append(f"{x['label']} ({pct[case]}): {mine} here, {noaa} in HYSPLIT")
    ahead = [c[k]["dep"]["yellow"][0] > c[k]["hy_dep"]["yellow"] for k in _order(fa)]
    farther = (
        "This site\u2019s model reaches farther in every case."
        if all(ahead)
        else "HYSPLIT reaches farther in every case."
        if not any(ahead)
        else "Neither model reaches farther in every case."
    )
    return line, rows, farther


def hysplit_compare_html(fa: Facts | None, pct: dict[str, str]) -> str:
    """Return the section on NOAA, HYSPLIT and how its result compares; empty without one."""
    if not fa or not all(x.get("hy_dep") for x in fa["cases"].values()):
        return ""
    line, rows, farther = _hysplit_result(fa, pct, html=True)
    what = HYSPLIT_WHAT.replace(
        f"({HYSPLIT_CITE})", f'(<a href="{HYSPLIT_URL}" rel="noopener">{HYSPLIT_CITE}</a>)'
    )
    return f"""
  <h3>{HYSPLIT_HEAD}</h3>
  <p>{NOAA_WHAT} {what}</p>
  <p>{HYSPLIT_HOW}</p>
  <p>{line}</p>
  <div class="tablewrap"><table>
    {HYSPLIT_TABLE_HEAD}
    <tbody>{"".join(rows)}</tbody></table></div>
  <p>{farther} {HYSPLIT_LIMIT}</p>"""


def hysplit_compare_plain(fa: Facts | None, pct: dict[str, str]) -> str:
    """Return the same comparison as one plain paragraph; empty without a HYSPLIT result."""
    if not fa or not all(x.get("hy_dep") for x in fa["cases"].values()):
        return ""
    line, rows, farther = _hysplit_result(fa, pct, html=False)
    return (
        f"{NOAA_WHAT} {HYSPLIT_WHAT} {HYSPLIT_HOW} {line} {'; '.join(rows)}. "
        f"{farther} {HYSPLIT_LIMIT} NOAA\u2019s page on HYSPLIT: {HYSPLIT_URL}."
    )


@dataclass(frozen=True)
class _Text:
    """Sentences shared by the summary, the FAQ and llms.txt."""

    model: str
    rows_html: list[str]
    rows_txt: list[str]
    town: str
    air_html: str
    air_plain: str
    amount: str
    pct: str
    weather: str
    forecast_line: str


def _text(f: Facts, ctx: dict[str, Any]) -> _Text:
    if f.get("n_models"):  # another day can have fewer models (RRFS may not reach it)
        ctx = {**ctx, "n_models": f["n_models"]}
    shown = f["shown_model"] or ""
    model = shown
    for code, short in MODEL_SHORT.items():
        model = model.replace(code, short)
    rows_html, rows_txt = _case_rows(f, ctx, model or "the main forecast")
    c, pct = f["cases"], ctx["pct"]
    return _Text(
        model=model,
        rows_html=rows_html,
        rows_txt=rows_txt,
        town=_town_text(f),
        air_html=_air_text(f, model, ctx["n_models"], html=True),
        air_plain=_air_text(f, model, ctx["n_models"], html=False),
        amount=(
            f"about {lb(f['azide_lb'])} pounds of lead azide in 68 drums, which holds about "
            f"{lb(f['lead_total_lb'])} pounds of lead"
        ),
        pct=", ".join(f"{CASE_WORD.get(k, c[k]['label'].lower())} {pct[k]}" for k in _order(f)),
        weather=_permit_weather_text(f),
        forecast_line=(
            f"Forecast pulled {ctx['got_txt']} from {ctx['n_models']} weather models; the map "
            f"shows {model or 'the first model'}."
        ),
    )


def _other_title(day: str, lead: str, *, question: bool = False) -> str:
    """Head the part about a day other than the one the summary leads with."""
    if day_num(day) < day_num(lead):  # an earlier planned day, since postponed
        if question:
            return f"What would the map show for {day}, an earlier planned date?"
        return f"{day}, an earlier planned date"
    return f"What if the blasts are on {day}?" if question else f"If the blasts are on {day}"


def _day_html(f: Facts, ctx: dict[str, Any], lead: str = PLANNED_DAY) -> str:
    """Return the summary section for another modeled day (f["day"], e.g. Tuesday)."""
    t = _text(f, ctx)
    note = window_note(f["day"])
    return f"""
  <h3>{_other_title(f["day"], lead)}</h3>
  <p>The map also models {f["day"]}; choose it under &ldquo;Day&rdquo; above the map. \
{note + " " if note else ""}{wind_sentence(f)} {path_sentence(f)} {t.forecast_line}</p>
  <div class="tablewrap"><table>
    {DEP_TABLE_HEAD}
    <tbody>{"".join(t.rows_html)}</tbody></table></div>
  <p>{t.town} Town checks use approximate town centers. {TOWN_CAVEAT}</p>
  <p>{REACH_NOTE}</p>
  <p>{t.air_html}</p>
  <p>{t.weather}</p>"""


def _day_plain(f: Facts, ctx: dict[str, Any]) -> list[str]:
    """Return llms.txt lines for another modeled day."""
    t = _text(f, ctx)
    return [
        (
            f"- {f['day']} (also modeled): "
            + (window_note(f["day"]) + " " if window_note(f["day"]) else "")
            + f"{wind_sentence(f)} "
            f"{path_sentence(f, html=False)} {t.forecast_line}"
        ),
        f"  {t.town} {TOWN_CAVEAT}",
        "  Farthest reach of ground lead (yellow 5, orange 40, red 100 \u00b5g/ft\u00b2):",
        *[f"  {r}" for r in t.rows_txt],
        f"  {REACH_NOTE}",
        f"  {t.air_plain}",
        f"  {t.weather}",
    ]


def _summary_html(f: Facts, ctx: dict[str, Any], t: _Text, more: list[Facts]) -> str:
    built = ctx["built_txt"]
    lead = f.get("day", PLANNED_DAY)
    on = f" on {lead}" if more else ""  # label the lead day's parts when there are more
    note = window_note(lead)
    no_time = time_note_html(built)
    return f"""<section id="summary" aria-labelledby="summary-h">
  <h2 id="summary-h">What the maps show</h2>
  <p class="caveat"><b>{CAVEAT}</b></p>
  <h3>When was the detonation?</h3>
  <p>{no_time}</p>
  {f'<p class="caveat">{ctx["pending_note"]}</p>' if ctx.get("pending_note") else ""}
  {_archived_html(ctx.get("archived"), ctx["pct"])}<h3>Where the cloud goes{on}</h3>
  <p>{note + " " if note else ""}{wind_sentence(f)} {path_sentence(f)} {t.forecast_line}</p>
  <h3>How far lead on the ground could reach{on}</h3>
  <p>Farthest distance from the plant where lead on the ground reaches each EPA dust-lead action
    level by the end of the 8-hour run, for a blast at {BLAST_TIME} The
    levels are 5 \u00b5g/ft\u00b2 (floors), 40 \u00b5g/ft\u00b2 (window sills), and \
100 \u00b5g/ft\u00b2
    (window troughs). They are for indoor dust, so outdoor lead is only a rough comparison. The
    first number uses the {t.model or "main"} forecast shown on the map. The smaller number \
below it is
    the farthest any of the {ctx["n_models"]} weather forecasts reaches, with either of two
    dry-deposition schemes (Zhang et al. 2001 and its revision by Emerson et al. 2020), which is
    what the map shows with &ldquo;weather-model spread&rdquo; turned on.</p>
  <div class="tablewrap"><table>
    {DEP_TABLE_HEAD}
    <tbody>{"".join(t.rows_html)}</tbody></table></div>
  <p>{t.town} Town checks use approximate town centers. {TOWN_CAVEAT}</p>
  <p>{REACH_NOTE}</p>
  <h3>Lead in the air{on}</h3>
  <p>{t.air_html}</p>
  <h3>How this compares with the Army\u2019s maps</h3>
  <p>{ARMY_COMPARE} Sources: <a href="{PERMIT_URL}" rel="noopener">{PERMIT_CITE}</a>; \
<a href="{ARMY_MAPS_PDF}" rel="noopener">{ARMY_MAPS_CITE}</a>.</p>
  <p>{t.weather}</p>{hysplit_compare_html(ctx.get("archived"), ctx["pct"])}\
{"".join(_day_html(m, ctx, lead) for m in more)}
  <h3>{ANALYSIS_QUESTION}</h3>
  <p>{ANALYSIS_HTML}</p>
  <h3>How sure is this?</h3>
  <p>Not very. The Army estimates that 26% of the lead gets into the air with its mitigation
    (an emission factor of 0.26), but no one has measured a blast like this, and the actual
    winds may have differed from the forecast. The four cases show the range. Use the map
    above to see each case. Last updated {built}.</p>
  <p>{PRECEDENT} Sources: {BRIEFING_SOURCES_HTML}.</p>
  <p>{RELEASE_POINT}</p>
  <h3>How the date was set</h3>
  <p>{TRUMP_HOLD} Sources: {TRUMP_SOURCE_HTML}.</p>
  <p>{WHY_WEDNESDAY} Source: {WEDNESDAY_SOURCE_HTML}.</p>
  <p><b>Court case.</b> {court_pause([m["day"] for m in more], lead)} Sources: \
{COURT_SOURCES_HTML}.</p>
  <p><b>{EARLIER_HEAD}</b> {WHY_TUESDAY} Sources: {TUESDAY_SOURCES_HTML}.
    {WHY_MONDAY} Source: <a href="{ARMY_URL}" rel="noopener">{ARMY_CITE}</a>.</p>
</section>"""


def _faq(f: Facts, ctx: dict[str, Any], t: _Text, more: list[Facts]) -> list[tuple[str, str]]:
    pct = ctx["pct"]
    lead = f.get("day", PLANNED_DAY)
    mon = f"For {lead}: " if more else ""  # the lead day's answers say so
    days = [
        (
            _other_title(m["day"], lead, question=True),
            f"The map also models {m['day']}. "
            + (window_note(m["day"]) + " " if window_note(m["day"]) else "")
            + f"{wind_sentence(m)} "
            f"{path_sentence(m, html=False)} {_text(m, ctx).town} {TOWN_CAVEAT} "
            "Farthest reach of ground lead: "
            + " ".join(r[2:] for r in _text(m, ctx).rows_txt)
            + " "
            + REACH_NOTE
            + " "
            + CAVEAT,
        )
        for m in more
    ]
    fa = ctx.get("archived")
    before = FORECAST_PREFIX if fa else ""
    opens = [(DEFAULT_VIEW_QUESTION, f"{_archived_plain(fa, pct)} {CAVEAT}")] if fa else []
    noaa = bool(hysplit_compare_plain(fa, pct))
    return [
        (
            "Is the Iowa Lead Tracker official?",
            "No. " + CAVEAT + " For instructions and health questions, follow the Army, your "
            "county emergency management office, and state health officials.",
        ),
        (
            "Who made the Iowa Lead Tracker, and why?",
            ABOUT_WHO + " The model code, saved weather forecasts, assumptions, and sources are "
            f"public at {SOURCE_URL} so anyone can check them.",
        ),
        (
            "When was the lead azide blast at the Iowa Army Ammunition Plant?",
            time_note(ctx["built_txt"])
            + f" (Source: {ADVISORY_NOV24_CITE}, {ADVISORY_NOV24_URL}.) How the date was set: "
            f"{TRUMP_HOLD} (Sources: {TRUMP_SOURCE_TEXT}.) The Army had "
            "planned Monday, Nov. 23. On Nov. 22, the government told the court, which had put "
            "the permit on hold, that the Army had postponed it to Tuesday, Nov. 24. "
            f"{court_pause([m['day'] for m in more], lead)} (Sources: {COURT_SOURCES_TEXT}.) "
            f"{WHY_WEDNESDAY} (Source: {WEDNESDAY_SOURCE_TEXT}.)"
            + f" Earlier dates: {WHY_TUESDAY} (Sources: {TUESDAY_SOURCES_TEXT}.) "
            f"{WHY_MONDAY} (Source: {ARMY_CITE}, {ARMY_URL}.)",
        ),
        *opens,
        (
            "Where could the lead go?",
            (
                f"{before}{mon}{wind_sentence(f)} {path_sentence(f, html=False)} {t.town} "
                f"{TOWN_CAVEAT} {CAVEAT}"
            ),
        ),
        (
            "How far could lead on the ground reach?",
            f"{before}{mon}Farthest distance where ground lead reaches EPA dust-lead action levels "
            "(yellow 5, orange 40, red 100 \u00b5g/ft\u00b2) by the end of an 8-hour run: "
            + " ".join(r[2:] for r in t.rows_txt)
            + " "
            + REACH_NOTE
            + " "
            + CAVEAT,
        ),
        *days,
        (
            "How much lead does the map assume?",
            (
                f"{t.amount[0].upper() + t.amount[1:]}, per an Army Sustainment Command "
                "spokesperson quoted by ABC News on Nov. 19, 2026 (EPA's permit lists 68 drums). "
                "The Army estimates an emission factor of 0.26 (26% of the lead airborne) for "
                "its mitigated blast. No one has measured a blast like this, so the map shows "
                "four cases: low "
                f"{pct['low']} (based on "
                f"EPA AP-42 blasting-cap tests), U.S. Army mitigated "
                f"{pct['mid']} (the emission factor of 0.26 in the Army's Nov. 24 "
                "\u201cmitigated\u201d plume maps), high "
                f"{pct['high']} (a rule from the same handbook for explosions), and EPA permit "
                f"{pct.get('permit', '100%')} (the emission factor EPA requires for the Army's "
                f"official plume maps). {PRECEDENT.removesuffix('.')} ({BRIEFING_CITE}). "
                f"{RELEASE_POINT}"
            ),
        ),
        ("How does this compare with the Army's official maps?", ARMY_COMPARE + " " + t.weather),
        *([(HYSPLIT_QUESTION, f"{hysplit_compare_plain(fa, pct)} {CAVEAT}")] if noaa else []),
        (ANALYSIS_QUESTION, f"{ANALYSIS_TEXT} {CAVEAT}"),
        ("What should I do?", SAFETY_ANSWER),
    ]


def _llms(f: Facts, ctx: dict[str, Any], t: _Text, more: list[Facts]) -> str:
    lead = f.get("day", PLANNED_DAY)
    mon = f"{lead}: " if more else ""  # the lead day's lines say so
    fa = ctx.get("archived")
    before = FORECAST_PREFIX if fa else ""  # the lines that describe the forecast maps
    modeled = sorted({lead, *(m["day"] for m in more)}, key=day_num)
    return "\n".join(
        [
            f"# {ctx['site_name']}",
            "",
            f"> {ctx['description']}",
            "",
            f"Important: {CAVEAT} Don't use it to decide if you're safe.",
            "",
            "## About",
            "",
            ABOUT_WHO,
            "",
            CONTACT_TEXT,
            "",
            "## Key facts",
            "",
            (
                f"- Blast: {BLAST_DONE} Planned for "
                "about 9 a.m. CST Wednesday, Nov. 25, 2026 (Army public safety "
                "advisory, Nov. 24; FEMA emergency alert, Nov. 24; the "
                "Acting Secretary of the Army had said Wednesday morning on X, Nov. 23, after the "
                "court ruling; President Trump had ordered a "
                "hold earlier that day, see Presidential hold); the Army had scheduled "
                "Wednesday on Nov. 22 (Army, Nov. 22), after "
                "Monday, Nov. 23 and Tuesday, Nov. 24 (Nov. 22 court filing); the court lifted its "
                "hold on the permit on Nov. 23 (see Court case), Iowa Army Ammunition "
                f"Plant, Middletown, Iowa ({ctx['lat']:.4f}, {ctx['lon']:.4f}). Blast times "
                f"modeled: {BLAST_TIME} CST, on " + ", ".join(modeled) + "."
            ),
            (
                f"- Time and official advice: {time_note(ctx['built_txt'])} Sources: "
                f"{ADVISORY_NOV24_URL}; {FEMA_CITE} (no public address)"
            ),
            (
                f"- Court case: {court_pause([m['day'] for m in more], lead)} "
                f"Sources: {COURT_SOURCES_TEXT}"
            ),
            *([f"- Note: {ctx['pending_note']}"] if ctx.get("pending_note") else []),
            f"- Presidential hold: {TRUMP_HOLD} Sources: {TRUMP_SOURCE_TEXT}",
            f"- Why Wednesday: {WHY_WEDNESDAY} Source: {WEDNESDAY_SOURCE_TEXT}",
            f"- Earlier date, Tuesday: {WHY_TUESDAY} Sources: {TUESDAY_SOURCES_TEXT}",
            f"- Earlier date, Monday: {WHY_MONDAY} Source: {ARMY_CITE}, {ARMY_URL}",
            (
                f"- Mitigation: {MISTING} Sources: {ADVISORY_NOV24_CITE}, {ADVISORY_NOV24_URL}; "
                f"{BRIEFING_SOURCES_TEXT}"
            ),
            f"- 1977 precedent: {PRECEDENT} Sources: {BRIEFING_SOURCES_TEXT}",
            f"- Release point: {RELEASE_POINT}",
            (
                f"- Assumed: {t.amount} (Army Sustainment Command spokesperson via ABC News, "
                f"19 Nov 2026; 68 drums per EPA's emergency permit). Share airborne: {t.pct}, "
                "all in breathable sizes."
            ),
            f"- Army comparison: {ARMY_COMPARE}",
            *(
                [f"- NOAA HYSPLIT comparison: {hysplit_compare_plain(fa, ctx['pct'])}"]
                if hysplit_compare_plain(fa, ctx["pct"])
                else []
            ),
            *(
                [f"- Default view and archived weather: {_archived_plain(fa, ctx['pct'])}"]
                if fa
                else []
            ),
            (
                "- EPA\u2019s monitors and the cloud\u2019s path (preliminary analysis): "
                f"{ANALYSIS_TEXT}"
            ),
            f"- {before}{mon}{t.weather}",
            f"- {before}{mon}{t.forecast_line}",
            f"- {before}{mon}"
            + (window_note(lead) + " " if window_note(lead) else "")
            + f"{wind_sentence(f)} {path_sentence(f, html=False)}",
            f"- {before}{mon}{t.town} {TOWN_CAVEAT}",
            (
                f"- {before}{mon}Farthest reach of ground lead at EPA dust-lead action levels "
                f"(yellow 5, orange 40, red 100 \u00b5g/ft\u00b2), for a blast at {BLAST_TIME}:"
            ),
            *[f"  {r}" for r in t.rows_txt],
            f"  {REACH_NOTE}",
            f"- {before}{mon}{t.air_plain}",
            *[line for m in more for line in _day_plain(m, ctx)],
            f"- Last updated {ctx['built_txt']}.",
            "",
            "## Sources",
            "",
            *SOURCES,
            "",
            "## Pages",
            "",
            f"- [Map]({ctx['site_url']}): interactive map by weather and case",
            (
                f"- [Preliminary analysis]({ANALYSIS_URL}): where EPA\u2019s real-time lead "
                "monitors sat, compared with the forecast and analyzed-weather paths"
            ),
            f"- [Source code]({SOURCE_URL}): the model, saved forecasts, assumptions and tests",
            f"- [Instagram @{INSTAGRAM_HANDLE}]({INSTAGRAM_URL}): updates",
            "",
        ]
    )


def render(
    f: Facts, ctx: dict[str, Any], more: list[Facts] | None = None
) -> tuple[str, list[tuple[str, str]], str]:
    """Return the summary section HTML, the FAQ (question, answer) pairs, and llms.txt.

    Parameters
    ----------
    f
        Output of :func:`facts` for the day the summary leads with; ``day`` names it
        (default :data:`PLANNED_DAY`).
    ctx
        Build facts: ``pct``, ``got_txt``, ``n_models``, ``built_txt``, ``site_name``,
        ``site_url``, ``description``, ``lat`` and ``lon``.
    more
        :func:`facts` for other modeled days, each with ``day`` ("Tuesday, Nov. 24") and,
        optionally, ``n_models``; described after the lead day.
    """
    more = more or []
    t = _text(f, ctx)
    return (
        _summary_html(f, ctx, t, more),
        _faq(f, ctx, t, more),
        _llms(f, ctx, t, more),
    )
