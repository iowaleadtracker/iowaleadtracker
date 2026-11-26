"""References and key assumptions for the iowaleadtracker.com page.

Written in American Meteorological Society (AMS) author-date style: one alphabetical
list, AMS journal abbreviations, bold volume numbers, "and Coauthors" past eight authors,
and in-text citations of the form Church (1969) or (MACTEC 2008).

Every entry was checked against the publisher, a library index, or the issuing agency on
20 November 2026. Used by make_map_picker.py.
"""

from __future__ import annotations

import datetime as dt
import html
from typing import Any
from zoneinfo import ZoneInfo

SITE_TZ = ZoneInfo("America/Chicago")  # the date readers are told they accessed the map
ASSUME_HEAD = (
    '<thead><tr><th scope="col">What</th><th scope="col">Value used</th>'
    '<th scope="col">Basis</th></tr></thead>'
)


def _a(url: str, text: str | None = None) -> str:
    return f'<a href="{html.escape(url)}" rel="noopener">{html.escape(text or url)}</a>'


def doi(d: str) -> str:
    """Return a link to a DOI, shown as its full https://doi.org/ address (AMS style)."""
    return _a(f"https://doi.org/{d}")


#: Where the model, saved forecasts, assumptions and tests are published.
SOURCE_URL = "https://github.com/iowaleadtracker/iowaleadtracker"
# The spread-method cross-check (HYSPLIT and tracer data) linked from the methodology table.
TURBULENCE_URL = SOURCE_URL + "/blob/main/TURBULENCE.md"
# The preliminary analysis of where EPA's real-time monitors sat: its page on the site
# (built by brief_page.py from the brief's README) and its folder in the repository.
ANALYSIS_PATH = "/monitor-placement/"
ANALYSIS_URL = "https://iowaleadtracker.com" + ANALYSIS_PATH
ANALYSIS_FOLDER = "scenarios/iowa-aap-lead-azide/postmortem/monitor-placement-brief"
ANALYSIS_FOLDER_URL = f"{SOURCE_URL}/tree/main/{ANALYSIS_FOLDER}"
#: The site's role inbox (no personal name; see the README's writing rules).
CONTACT_EMAIL = "contact@iowaleadtracker.com"
#: The site's Instagram account, for updates.
INSTAGRAM_HANDLE = "iowaleadtracker"
INSTAGRAM_URL = f"https://www.instagram.com/{INSTAGRAM_HANDLE}/"
#: Said wherever these appear, so neither is read as a safety hotline.
CONTACT_LIMIT = "Neither can tell you whether you\u2019re safe; follow official instructions."
CONTACT_HTML = (
    f'Questions or corrections: <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>. '
    f'Updates: <a href="{INSTAGRAM_URL}" rel="noopener">Instagram @{INSTAGRAM_HANDLE}</a>. '
    f"{CONTACT_LIMIT}"
)
CONTACT_TEXT = (
    f"Questions or corrections: {CONTACT_EMAIL}. Updates: Instagram @{INSTAGRAM_HANDLE}, "
    f"{INSTAGRAM_URL}. {CONTACT_LIMIT}"
)
#: News stories that mention the Iowa Lead Tracker, newest first: (outlet, date, URL).
#: Link the original publisher, not a syndicated copy (the Free Press story also ran on
#: Yahoo News). Add one only after reading what it says about the map.
MENTIONS_HEAD = "Mentions of the Iowa Lead Tracker."
MENTIONS = [
    # J. Williams, "Army's munition explosion plans delayed. How it could change the risks,"
    # updated Nov. 23, 2026, 3:40 p.m. ET; read in full Nov. 23. It says: "Initial maps
    # showed the lead plume extending northward, however, the Iowa Lead Tracker website now
    # shows the plume potentially moving southwest."
    (
        "Detroit Free Press",
        "Nov. 23, 2026",
        (
            "https://www.freep.com/story/news/local/michigan/2026/11/23/"
            "army-lead-azide-munitions-michigan-explosion/92924794007/"
        ),
    ),
]
MENTIONS_HTML = (
    "; ".join(
        f'<a href="{url}" rel="noopener">{outlet}</a>, {date}' for outlet, date, url in MENTIONS
    )
    + "."
)
ACCESSED = "accessed 20 November 2026"

# Alphabetical by first author, then year. HTML.
REFERENCES = [
    "AMS, 2026: Rain. Glossary of Meteorology, American Meteorological Society, accessed "
    "23 November 2026, " + _a("https://glossary.ametsoc.org/wiki/Rain") + ".",
    "Associated Press, 2026: Federal appeals court clears way for U.S. Army to detonate "
    "degraded bomb-making material in Iowa. Published by KCRG-TV9, 23 November 2026, accessed "
    "23 November 2026, "
    + _a(
        "https://www.kcrg.com/2026/11/23/"
        "federal-appeals-court-clears-way-us-army-detonate-degraded-bomb-making-material-iowa/"
    )
    + ".",
    (
        "Aurell, J., B. K. Gullett, D. Tabor, R. K. Williams, W. Mitchell, and M. R. Kemme, 2015: "
        "Aerostat-based sampling of emissions from open burning and open detonation of military "
        "ordnance. <i>J. Hazard. Mater.</i>, <b>284</b>, 108&ndash;120."
    ),
    "Barad, M. L., Ed., 1958: Project Prairie Grass, a field program in diffusion. Geophys. "
    "Res. Pap. 59, AFCRC-TR-58-235, Air Force Cambridge Research Center; data as distributed "
    "by J. S. Irwin, " + _a("https://harmo.org/jsirwin/Tracer_Data.html") + ".",
    "Barton, T., and R. Opsahl, 2026: Court lifts administrative stay, allowing lead azide "
    "detonation to move forward. Iowa Public Radio, 22 November 2026, updated 23 November 2026, "
    "accessed 23 November 2026, "
    + _a(
        "https://www.iowapublicradio.org/ipr-news/2026-11-23/court-lifts-stay-block-iowa-lead-detonation"
    )
    + ".",
    "Billingham, E., and T. Barton, 2026: What public health experts say about Friday&rsquo;s "
    "lead azide detonation. Iowa Public Radio, 19 November 2026, "
    f"{ACCESSED}, "
    + _a(
        "https://www.iowapublicradio.org/environment/2026-11-19/army-lead-detonation-public-health-safety-risks"
    )
    + ".",
    (
        "Briggs, G. A., 1973: Diffusion estimation for small emissions. ATDL Contribution File "
        "No. 79, Atmospheric Turbulence and Diffusion Laboratory, NOAA."
    ),
    "Church, H. W., 1969: Cloud rise from high-explosives detonations. Sandia Laboratories "
    "Rep. SC-RR-68-903, " + _a("https://www.osti.gov/biblio/4798257") + ".",
    (
        "Cunningham, E., 1910: On the velocity of steady fall of spherical particles through fluid "
        "medium. <i>Proc. Roy. Soc. London</i>, <b>83A</b>, 357&ndash;365."
    ),
    "Deliso, M., and J. M. Volack, 2026: Army postpones plan to detonate nearly 10,000 pounds of "
    "lead azide until Monday. ABC News, 19 November 2026, "
    f"{ACCESSED}, "
    + _a("https://abcnews.com/US/iowa-army-plant-lead-azide-detonation/story?id=138261613")
    + ".",
    "DOE, 1994: Airborne release fractions/rates and respirable fractions for nonreactor "
    "nuclear facilities. DOE-HDBK-3010-94, U.S. Department of Energy (reaffirmed 2013), "
    + _a(
        "https://www.energy.gov/sites/prod/files/2018/02/f48/DOE%202013_HDBK-3010-94%20Airborne%20Release%20Fractions_0.pdf"
    )
    + ".",
    "DOE, 2025: Protective Action Criteria (PAC) database. U.S. Department of Energy, data "
    f"exported 3 December 2025, {ACCESSED}, " + _a("https://emhub1.energy.gov/pacteel") + ".",
    "Dowell, D. C., and Coauthors, 2022: The High-Resolution Rapid Refresh (HRRR): An hourly "
    "updating convection-allowing forecast model. Part I: Motivation and system description. "
    "<i>Wea. Forecasting</i>, <b>37</b>, 1371&ndash;1395, " + doi("10.1175/WAF-D-21-0151.1") + ".",
    "Emerson, E. W., and Coauthors, 2020: Revisiting particle dry deposition and its role in "
    "radiative effect estimates. <i>Proc. Natl. Acad. Sci. USA</i>, <b>117</b>, "
    "26&thinsp;076&ndash;26&thinsp;082, " + doi("10.1073/pnas.2014761117") + ".",
    "EPA Region 7, 2026: Iowa Army Ammunition Plant response data viewer (real-time lead "
    "monitors and air sampling stations). ArcGIS Experience, U.S. Environmental Protection "
    "Agency, accessed 25 November 2026, "
    + _a("https://experience.arcgis.com/experience/1ddcf8b9d8314971b00dac8893ae9cd6")
    + ".",
    (
        "EPA, 1978: National ambient air quality standards for lead. <i>Fed. Regist.</i>, "
        "<b>43</b>, "
        "46246."
    ),
    (
        "EPA, 2008: National ambient air quality standards for lead. <i>Fed. Regist.</i>, "
        "<b>73</b>, "
        "66964. Codified at 40 CFR 50.16."
    ),
    (
        "EPA, 2016: Review of the national ambient air quality standards for lead. <i>Fed. "
        "Regist.</i>, <b>81</b>, 71906."
    ),
    (
        "EPA, 2024: Reconsideration of the dust-lead hazard standards and dust-lead "
        "post-abatement clearance levels. <i>Fed. Regist.</i>, <b>89</b>, 89456. Codified at "
        "40 CFR 745.227(e)(8)(viii)."
    ),
    "EPA, 2026: Emergency hazardous waste management facility permit for storage and treatment "
    "of lead azide, Iowa Army Ammunition Plant. EPA RCRA ID IA7213820445, U.S. EPA Region 7, "
    "13 November 2026, "
    + _a(
        "https://www.epa.gov/system/files/documents/2026-11/iaaap-emergency-permit-for-treatment-and-storage-final_redacted.pdf"
    )
    + ".",
    "EPA, cited 2026: AP-42, fifth edition, volume I, chapter 15: Ordnance detonation. U.S. "
    "Environmental Protection Agency, "
    + _a(
        "https://www.epa.gov/air-emissions-factors-and-quantification/ap-42-fifth-edition-volume-i-chapter-15-ordnance"
    )
    + ".",
    (
        "FEMA, 2026: Imminent Threat Alert: planned, controlled detonation at Iowa Army "
        "Ammunition Plant in Middletown Wed, Nov 25 at 9 AM. Wireless Emergency Alert, Federal "
        "Emergency Management Agency, 24 November 2026 (as received on a phone near the plant; "
        "no public web address)."
    ),
    "Finn, D., K. L. Clawson, R. M. Eckman, H. Liu, E. S. Russell, Z. Gao, and S. Brooks, "
    "2016: Project Sagebrush: Revisiting the value of the horizontal plume spread parameter "
    "&sigma;<sub>y</sub>. <i>J. Appl. Meteor. Climatol.</i>, <b>55</b>, 1305&ndash;1322, "
    + doi("10.1175/JAMC-D-15-0283.1")
    + ".",
    "Fournier, J. D., 1999: Reflectivity-rainfall rate relationships in operational meteorology. "
    "National Weather Service Forecast Office, Tallahassee, FL, accessed 23 November 2026, "
    + _a("https://www.weather.gov/tae/research-zrpaper")
    + ".",
    (
        "Gifford, F. A., 1961: Use of routine meteorological observations for estimating "
        "atmospheric dispersion. <i>Nucl. Saf.</i>, <b>2</b> (4), 47&ndash;51."
    ),
    "Harris, C. R., and Coauthors, 2020: Array programming with NumPy. <i>Nature</i>, <b>585</b>, "
    "357&ndash;362, " + doi("10.1038/s41586-020-2649-2") + ".",
    "Homann, S. G., and F. Aluzzi, 2013: HotSpot health physics codes, version 3.0: User&rsquo;s "
    "guide. LLNL-SM-636474, Lawrence Livermore National Laboratory, "
    + _a("https://narac.llnl.gov/hotspot")
    + ".",
    "Iowa Environmental Mesonet, 2026: ASOS observations for Burlington (BRL), Fort Madison "
    "(FSW) and Mount Pleasant (MPZ), Iowa, 25 November 2026, 8:30&ndash;10:30 a.m. CST. Iowa "
    "State University, accessed 26 November 2026, "
    + _a("https://mesonet.agron.iastate.edu/request/download.phtml?network=IA_ASOS")
    + ".",
    "Iowa HHS, 2026: Planned lead azide detonation fact sheet&mdash;November 23, 2026. Iowa "
    f"Department of Health and Human Services, {ACCESSED}, "
    + _a("https://hhs.iowa.gov/media/19822/download?inline=")
    + ".",
    "Iowa&rsquo;s News Now, 2026: Middletown officials say normal activities can resume "
    "following lead azide detonation. CBS2 Iowa, 25 November 2026, accessed 25 November 2026, "
    + _a(
        "https://cbs2iowa.com/news/local/"
        "middletown-officials-say-normal-activities-can-resume-following-lead-azide-detonation"
    )
    + ".",
    "KCCI, 2026: Court records: Army plans to detonate lead azide by Tuesday. KCCI 8 News, "
    "22 November 2026, accessed 22 November 2026, "
    + _a("https://www.kcci.com/article/lead-azide-bomb-detonation-iowa-tuesday/74499570")
    + ".",
    "KCRG, 2026: Trump orders the Army not to detonate bomb-making chemicals in Iowa without "
    "court approval. KCRG-TV9, 23 November 2026, accessed 23 November 2026, "
    + _a("https://www.kcrg.com/2026/11/23/president-trump-orders-military-pause-iowa-detonation/")
    + ".",
    "Lis, A., 2026: Here&rsquo;s how Army plans to minimize toxic lead dust following Iowa "
    "ammunitions blast. Shaw Local, 24 November 2026, accessed 25 November 2026, "
    + _a(
        "https://www.shawlocal.com/news/2026/11/24/"
        "heres-how-army-plans-to-minimize-toxic-lead-dust-following-iowa-ammunitions-blast/"
    )
    + ".",
    "MACTEC Federal Programs, 2008: Emission factors developed based on Exploding Ordnance "
    "Emission Study Phase II Series 7 testing conducted at Aberdeen Proving Ground, Maryland. "
    "Draft background report, AP-42 5th ed., Chapter 15, U.S. Army Environmental Command and "
    "U.S. EPA, "
    + _a("https://www.epa.gov/sites/default/files/2020-11/documents/b15_eo7_draft_feb08.pdf")
    + ".",
    "McFate, L., 2026a: Postponed: Lead azide detonation. U.S. Army Sustainment Command, "
    f"19 November 2026, {ACCESSED}, " + _a("https://www.army.mil/article/296926") + ".",
    "McFate, L., 2026b: Public safety advisory: Controlled, mitigated detonation of unstable "
    "[lead azide]. U.S. Army Sustainment Command, 24 November 2026, accessed 24 November "
    "2026, " + _a("https://www.army.mil/article/297039") + ".",
    "McFate, L., 2026c: Today&rsquo;s controlled detonation at Iowa Army Ammunition Plant. U.S. "
    "Army Sustainment Command, 25 November 2026 (text checked from the maintainer&rsquo;s "
    "screenshot; army.mil refuses this site&rsquo;s tools), "
    + _a("https://www.army.mil/article/297089")
    + ".",
    "McFate, L., 2026d: Deposition maps as of 3:00 PM (CST) &ndash; lead azide. U.S. Army "
    "Sustainment Command, 25 November 2026, accessed 25 November 2026, "
    + _a("https://www.army.mil/article/297109")
    + ".",
    "New York Times, 2026: Live coverage of the Iowa lead azide detonation. <i>The New York "
    "Times</i>, 25 November 2026 (read by the maintainer; not fetched by this site&rsquo;s "
    "tools, which nytimes.com blocks), "
    + _a("https://www.nytimes.com/live/2026/11/25/us/iowa-detonation-ammunition-news")
    + ".",
    "NOAA, 2025: Radar images: Reflectivity. NOAA JetStream, last updated 11 March 2025, "
    "accessed 23 November 2026, " + _a("https://www.noaa.gov/jetstream/reflectivity") + ".",
    (
        "Pasquill, F., 1961: The estimation of the dispersion of windborne material. <i>Meteor. "
        "Mag.</i>, <b>90</b>, 33&ndash;49."
    ),
    "Purpura, P., 2026: What else could the lead azide blast release? KCCI 8 News, 24 November "
    "2026, accessed 25 November 2026, "
    + _a(
        "https://www.kcci.com/article/what-else-could-a-lead-azide-detonation-release-in-eastern-iowa/"
        "74526545"
    )
    + ".",
    (
        "Schiller, L., and A. Naumann, 1933: &Uuml;ber die grundlegenden Berechnungen bei der "
        "Schwerkraftaufbereitung. <i>Z. Ver. Dtsch. Ing.</i>, <b>77</b>, 318&ndash;320."
    ),
    (
        "Scire, J. S., D. G. Strimaitis, and R. J. Yamartino, 2000: <i>A User&rsquo;s Guide for "
        "the CALPUFF Dispersion Model (Version 5)</i>. Earth Tech, Inc., "
        + _a("https://calpuff.org/calpuff/download/CALPUFF_UsersGuide.pdf")
        + "."
    ),
    (
        "Seinfeld, J. H., and S. N. Pandis, 2016: <i>Atmospheric Chemistry and Physics: From Air "
        "Pollution to Climate Change</i>. 3rd ed. Wiley."
    ),
    (
        "Slinn, W. G. N., 1984: Precipitation scavenging. <i>Atmospheric Science and Power "
        "Production</i>, D. Randerson, Ed., DOE/TIC-27601, U.S. Department of Energy, "
        "466&ndash;532. "
        "(Also cited as 1983.)"
    ),
    "Stein, A. F., R. R. Draxler, G. D. Rolph, B. J. B. Stunder, M. D. Cohen, and F. Ngan, 2015: "
    "NOAA&rsquo;s HYSPLIT atmospheric transport and dispersion modeling system. <i>Bull. Amer. "
    "Meteor. Soc.</i>, <b>96</b>, 2059&ndash;2077, " + doi("10.1175/BAMS-D-14-00110.1") + ".",
    "Steindler, M. J., and W. B. Seefeldt, 1980: A method for estimating the challenge to an "
    "air cleaning system resulting from an accidental explosive event. <i>Proc. 16th DOE "
    "Nuclear Air Cleaning Conf.</i>, U.S. Department of Energy, 1155&ndash;1174, "
    + _a("https://www.osti.gov/biblio/6350910")
    + ".",
    (
        "Stokes, G. G., 1851: On the effect of the internal friction of fluids on the motion of "
        "pendulums. <i>Trans. Cambridge Philos. Soc.</i>, <b>9</b>, 8&ndash;106."
    ),
    (
        "Stull, R. B., 1988: <i>An Introduction to Boundary Layer Meteorology</i>. Kluwer "
        "Academic, 666 pp."
    ),
    (
        "Turner, D. B., 1970: <i>Workbook of Atmospheric Dispersion Estimates</i>. Rev. ed. Public "
        "Health Service Publ. 999-AP-26, National Air Pollution Control Administration."
    ),
    # Text checked from the maintainer's screenshot (Nov. 23, about 11 p.m. CST); the
    # permalink is from the maintainer.
    "U.S. Army, 2026a: &ldquo;&hellip;which will occur this Wednesday morning, as previously "
    "scheduled, based on forecast wind conditions.&rdquo; Post by the Acting Secretary "
    "of the Army (@SecArmy) on X, 23 November 2026, accessed 23 November 2026, "
    + _a("https://x.com/SecArmy/status/2125060405605154940")
    + ".",
    "U.S. Army, 2026b: &ldquo;The controlled detonation at Iowa Army Ammunition Plant is now "
    "scheduled on Wednesday, November 25, 2026&hellip;&rdquo; Post by the U.S. Army on "
    "Facebook, 22 November 2026, accessed 23 November 2026, "
    + _a("https://www.facebook.com/story.php?story_fbid=1611961230959211&id=100064360494281")
    + ".",
    (
        "U.S. Army, 2026c: Public advisory: Potential exposure to toxic lead dust. "
        "&ldquo;Mitigated 0.26&rdquo; deposition and dispersion maps for a detonation at "
        "0900 CST, 25 November 2026. U.S. Army Sustainment Command, issued 24 November "
        "2026, linked from McFate (2026b), "
        + _a("https://d34w7g4gy10iej.cloudfront.net/pubs/pdf_78382.pdf")
        + "."
    ),
    "U.S. Army, 2026d: Public and media advisory regarding the detonation of lead azide at Iowa "
    "Army Ammunition Plant in Middletown, Iowa. U.S. Army Sustainment Command, 18 November 2026, "
    + _a("https://d34w7g4gy10iej.cloudfront.net/pubs/pdf_78366.pdf")
    + ".",
    "U.S. Department of Justice, 2026: Respondents&rsquo; notice of the Army&rsquo;s intent to "
    "respond to immediate threat under RCRA&rsquo;s emergency exclusion. <i>Iowa Environmental "
    "Council v. U.S. Environmental Protection Agency</i>, No. 26-3374, U.S. Court of Appeals for "
    "the Eighth Circuit, filed 21 November 2026, with the declaration of Col. A. C. Teller, "
    "accessed 22 November 2026, "
    + _a(
        "https://s3.documentcloud.org/documents/28930203/"
        "iowa-environmental-council-v-us-environmental-protection-agency.pdf"
    )
    + ".",
    "U.S. Department of Justice, 2026: Respondents&rsquo; opposition to petitioners&rsquo; "
    "emergency motion for stay. <i>Iowa Environmental Council v. U.S. Environmental Protection "
    "Agency</i>, No. 26-3374, U.S. Court of Appeals for the Eighth Circuit, filed 22 November "
    "2026, accessed 23 November 2026, "
    + _a(
        "https://storage.courtlistener.com/recap/gov.uscourts.ca8.116088/"
        "gov.uscourts.ca8.116088.805661522.0.pdf"
    )
    + ".",
    "Zhang, L., S. Gong, J. Padro, and L. Barrie, 2001: A size-segregated particle dry "
    "deposition scheme for an atmospheric aerosol module. <i>Atmos. Environ.</i>, <b>35</b>, "
    "549&ndash;560, " + doi("10.1016/S1352-2310(00)00326-5") + ".",
    "Zippenfenig, P., 2023: Open-Meteo.com Weather API. Zenodo, software, "
    + doi("10.5281/zenodo.7970649")
    + ".",
]

MODEL_CREDITS = {  # Open-Meteo model name -> who runs it
    "gfs_global": "NOAA NCEP (GFS)",
    "gfs_seamless": "NOAA NCEP (GFS, with HRRR for the first two days)",
    "ncep_hrrr_conus": "NOAA NCEP (HRRR)",
    "ncep_rrfs_conus": "NOAA NCEP (RRFS)",
    # its mixing height comes from the same forecast's 9 km data (met.MIXING_HEIGHT_FROM)
    "ecmwf_ifs025": "ECMWF (IFS 0.25&deg;, with the mixing height from IFS 9 km)",
    "icon_seamless": "DWD (ICON)",
    "gem_seamless": "Environment and Climate Change Canada (GEM)",
    "ukmo_seamless": "the UK Met Office",
    "meteofrance_seamless": "M&eacute;t&eacute;o-France",
}


def data_credits(models: list[str]) -> str:
    """Return the data and map credits, naming only the forecast models the maps used."""
    names = [MODEL_CREDITS.get(m, html.escape(m)) for m in models] or ["the forecast models used"]
    listed = names[0] if len(names) == 1 else ", ".join(names[:-1]) + ", and " + names[-1]
    return (
        f"Forecast data from {listed}, through Open-Meteo. Basemaps: Esri and its data "
        "providers (World Light Gray Canvas, World Dark Gray Canvas, World Topographic Map, and "
        "World Imagery), including &copy; "
        + _a("https://www.openstreetmap.org/copyright", "OpenStreetMap contributors")
        + " (Open Database License)."
    )


def assumptions(ctx: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Return the key-assumption table as (what, value, basis) rows of HTML.

    Parameters
    ----------
    ctx
        Build facts: ``pct`` (share airborne per case), ``n_models`` (spelled-out count),
        ``got_txt`` (forecast download time) and ``shown_model`` (model on the map).
    """
    p = ctx["pct"]
    return [
        (
            "Amount destroyed",
            "About 9,700 lb (4,400 kg) of lead azide, Pb(N<sub>3</sub>)<sub>2</sub>, in 68 drums",
            (
                "Army Sustainment Command spokesperson (Deliso and Volack 2026); 68 drums "
                "(EPA 2026, where the weight is redacted). The Army has also been quoted at 9,500 "
                "lb "
                "(Billingham and Barton 2026)"
            ),
        ),
        (
            "Lead in lead azide",
            "71.1% by mass (207.2 &divide; 291.24), about 6,900 lb",
            "Standard atomic weights",
        ),
        (
            "Energy",
            "1.64 MJ/kg; TNT equivalent at 4.184 MJ/kg",
            "Assumed; the model was checked from 1.4 to 1.64 MJ/kg",
        ),
        (
            "Charges",
            (
                "Two equal blasts inside earth-covered magazines at about 9 a.m. Wednesday "
                "(McFate 2026b; FEMA 2026); 8:30 and 9:30 a.m. were also modeled until Nov. 26"
            ),
            (
                "Two detonations at about noon on the earlier Monday date (Iowa HHS 2026); drums "
                "detonated in place in the "
                "magazines, "
                "simultaneously or in rapid succession (EPA 2026)"
            ),
        ),
        (
            "Cloud height",
            (
                "H = 76&middot;W<sup>&frac14;</sup> (H in m, W in lb TNT per charge), "
                "halved for earth cover"
            ),
            (
                "Church (1969), as used in HotSpot (Homann and Aluzzi 2013); "
                "the halving is a screening assumption, not validated"
            ),
        ),
        (
            "Starting cloud",
            (
                "5 layers from the ground to the cloud top; starting width "
                "&sigma;<sub>y</sub> = 0.25 &times; cloud top"
            ),
            "Assumed",
        ),
        (
            "Lead in the air",
            (
                f"Low {p['low']}, U.S. Army mitigated {p['mid']}, high {p['high']}, EPA permit "
                f"{p['permit']} of the lead; the rest stays at the site"
            ),
            (
                "Low: floor from AP-42 "
                "blasting-cap tests (MACTEC 2008). High: TNT-equivalent rule (DOE 1994; Steindler "
                "and "
                "Seefeldt 1980). U.S. Army mitigated: the emission factor of 0.26 in the "
                "Army&rsquo;s Nov. "
                "24 &ldquo;Mitigated 0.26&rdquo; plume maps (U.S. Army 2026c). "
                "EPA permit: the emission factor of 1.00 EPA "
                "requires "
                "for the Army&rsquo;s plume maps (EPA 2026)"
            ),
        ),
        (
            "Particle sizes",
            "0.3, 1, 3, and 10 &micro;m (30/40/20/10% by mass) at 9,500 kg/m&sup3; (lead oxide)",
            (
                "Assumed metal-fume mix; 96&ndash;98% of dust from blasting caps was "
                "under 10 &micro;m (MACTEC 2008)"
            ),
        ),
        (
            "Weather",
            (
                "Archived weather (the map opens on it): NOAA&rsquo;s HRRR model as served at "
                "6:51 p.m. CST on Nov. 25, after the eight hours modeled had passed; one "
                "weather source, two deposition schemes. Forecast "
                "(before the blast): "
                f"{ctx['n_models']} forecast models pulled "
                f"{ctx['got_txt']}; "
                f"{html.escape(ctx['shown_model'])} shown; &plusmn;5&deg; direction error around "
                "each"
            ),
            (
                "Open-Meteo (Zippenfenig 2023); Dowell et al. (2022); 5 &times; 5 grid of points "
                "around the plant"
            ),
        ),
        (
            "Cloud spread",
            (
                "Grows with the turbulence at each puff, worked out from the forecast wind, "
                "sunshine, cloud, temperature and mixing height (the turbulence option of the "
                "CALPUFF model). Crosswind growth is set to a 10-minute basis, which keeps the "
                "cloud somewhat narrower and the levels along its path higher than a 1-hour "
                "basis would. Until Nov. 24: stability-class curves (Briggs rural)"
            ),
            (
                "Scire et al. (2000); stability classes, still used for minimum vertical "
                "turbulence: Pasquill (1961); Gifford (1961); Turner (1970); earlier curves: "
                "Briggs (1973)"
            ),
        ),
        (
            "Spread cross-check",
            (
                "Checked against measured spread in two tracer experiments and against "
                "NOAA&rsquo;s HYSPLIT model on four past days. It gives about 0.8 times the "
                "measured crosswind spread, on purpose, and puts the edges of the levels at "
                "0.9&ndash;2.4 times HYSPLIT&rsquo;s distances; the earlier curves gave about half "
                "the spread measured in the more recent test and up to 5 times HYSPLIT&rsquo;s "
                "distances. Real levels "
                "can still be higher or lower than shown. Right next to the plant, including "
                "Middletown, a few degrees of wind decide the levels, which can be several "
                "times higher or lower than shown. In calm evening and night air, plumes can "
                "swing across a far wider arc than the map&rsquo;s &plusmn;5&deg; direction "
                "view. Details: " + _a(TURBULENCE_URL, "TURBULENCE.md")
            ),
            "Barad (1958); Stein et al. (2015); Finn et al. (2016)",
        ),
        (
            "Evening mixing layer",
            (
                "When the forecast mixing height falls around sunset, the part of "
                "the cloud above the new top stays aloft as a residual layer: it travels on but "
                "doesn&rsquo;t "
                "reach the ground unless the layer grows back into it"
            ),
            "Stull (1988)",
        ),
        (
            "Settling",
            (
                "Stokes settling with slip correction; Schiller&ndash;Naumann drag for "
                "larger particles"
            ),
            "Stokes (1851); Cunningham (1910); Schiller and Naumann (1933)",
        ),
        (
            "Deposition",
            (
                "Size-resolved dry deposition over harvested cropland (late autumn); the "
                "weather-model spread also runs each forecast with a revised scheme, which "
                "over cropland deposits particles under about 0.5 &micro;m more slowly and "
                "larger ones faster; rain washout "
                "10<sup>&minus;4</sup> "
                "s<sup>&minus;1</sup> per mm/h"
            ),
            (
                "Zhang et al. (2001), crops and mixed farming, late autumn after frost; "
                "Emerson et al. (2020), SI Table S1; "
                "Slinn (1984); Seinfeld and Pandis (2016)"
            ),
        ),
        (
            "Run",
            "8 hours after the blast, 60-second steps, grid cells about 0.4 mi (0.67 km)",
            "Model settings",
        ),
        (
            "Not modeled",
            (
                "Terrain, buildings, lead stirred back up from the ground, the blast "
                "itself, gases, and the Army&rsquo;s soil soaking and water misters"
            ),
            (
                "Model limits. The Army&rsquo;s 0.26 estimate covers its sand barriers, water "
                "wall, gel blocks, foam and misters (U.S. Army 2026c); here, runs of "
                "the model&rsquo;s "
                "spray option with guessed setups (528&ndash;26,000 gal/min) caught 0.1&ndash;19% "
                "of the "
                "lead (U.S. Army 2026d; Slinn 1984; Seinfeld and Pandis 2016)"
            ),
        ),
        (
            "Levels of concern",
            (
                "Ground: EPA dust-lead action levels for indoor wipe samples. Air: "
                "lead NAAQS (3-month averages) and DOE PAC-1 (60 minutes)"
            ),
            (
                "EPA (2008, 2024); DOE (2025). The permit uses the same 5 and 100 "
                "&micro;g/ft&sup2; as its "
                "map lines (EPA 2026). Compared with modeled outdoor values only as a rough guide"
            ),
        ),
    ]


#: The short methodology note that opens the Methodology and References dialog. Every fact
#: in it is in the key-assumptions table, with its source.
#: The short note that opens the Methodology and References dialog. Every fact in it is in
#: the key-assumptions table below it, with its source.
METHOD_HEAD = "How the map works."


def method_intro(pct: dict[str, str]) -> str:
    """Return the methodology note, with the release cases' shares from the build."""
    return (
        "The map uses a Gaussian puff model, the same kind of model behind emergency-response "
        f"software such as {_a('https://narac.llnl.gov/hotspot', 'HotSpot')} (Homann and "
        "Aluzzi 2013). A puff fits a one-time explosion "
        "better than a model of a steady plume from a smokestack. The model tracks only the "
        "lead: lead azide "
        "is 71.1% lead by weight, so about 9,700 lb of it holds about 6,900 lb of lead. How "
        "high the cloud starts comes from Church (1969). No one has measured how much of the "
        "lead gets airborne in a blast like this, so the map runs four cases instead of picking "
        f"one most likely number: {pct['permit']}, which EPA\u2019s permit requires the Army to "
        "assume for its official plume maps and which the map shows first as the worst case, "
        f"and {pct['high']} (high), {pct['mid']} (U.S. Army mitigated) and {pct['low']} (low). "
        "The high and low cases come from Department of Energy and Army\u2013EPA research; the "
        "U.S. Army mitigated case is the "
        "emission factor of 0.26 in the Army\u2019s Nov. 24 \u201cmitigated\u201d plume maps. "
        "That share is the most important number to check. The cloud "
        "spreads at a rate set "
        "by the forecast\u2019s turbulence, with the formulas of the CALPUFF model (Scire et al. "
        "2000); since Nov. 24 this replaces older curves that kept the cloud too narrow over "
        "hours (see the change log below). Every setting and its source is in the "
        "key-assumptions table."
    )


#: How the analysis after the blast was made, shown under the method note.
ANALYSIS_HEAD = "The analysis after the blast."
ANALYSIS_METHOD = (
    f'The <a href="{ANALYSIS_PATH}">preliminary analysis</a> of where EPA&rsquo;s real-time '
    "lead monitors sat runs this model twice: on the forecast the map showed at 9 a.m. on "
    "Nov. 25, and on NOAA&rsquo;s hourly analyses of that morning&rsquo;s weather from the "
    "HRRR system (Dowell et al. 2022). It also runs NOAA&rsquo;s HYSPLIT model (Stein et al. "
    "2015) on NOAA&rsquo;s archive of HRRR. It models the release from two magazines that a "
    "reader pointed to and that match published imagery; no official source confirms that "
    "location. It places the Army&rsquo;s map by the county lines printed on it. The "
    "results are model estimates, not measurements, and no one outside the project has "
    f"reviewed them. The text, the code, and the data are on {_a(ANALYSIS_FOLDER_URL, 'GitHub')}."
)

#: What changed in the maps and their method, newest first (Central time dates). Add an
#: entry for every change to the model, its settings or its sources.
CHANGES_HEAD = "Change log"
CHANGES = [
    (
        "Nov. 26",
        (
            "The page gives the blast time as 9:00 a.m. CST, from the Army&rsquo;s own 3 p.m. "
            "maps (&ldquo;DTG: 25NOV2026 0900 CST&rdquo;), and adds the weather observed at "
            "blast time at the Burlington, Fort Madison and Mount Pleasant airports (Iowa "
            "Environmental Mesonet): northeast winds of about 7 to 12 mph, close to the "
            "archived and forecast winds, and clear skies, unlike the forecast&rsquo;s 100% "
            "cloud cover. The maps did not change."
        ),
    ),
    (
        "Nov. 26",
        (
            "The map now opens on a 9 a.m. blast, the low case, and archived weather "
            "(NOAA&rsquo;s HRRR model as served at 6:51 p.m. CST on Nov. 25, after the hours "
            "modeled had passed). Opening on the low case is not a finding that little lead "
            "got out. A new Weather menu also has the forecast shown before the "
            "blast; those maps did not change. Before, the map opened on the EPA permit case "
            "and showed only the forecast. The 8:30 and 9:30 a.m. blast times are gone; 9 a.m. is "
            "the time the Army had set. The archived-weather maps start the cloud midway between "
            "the two magazines the blasts were in (40.8096, &minus;91.2692), from a "
            "reader&rsquo;s tip checked against published imagery and video; the forecast maps "
            "still start it at the point for the whole plant. The summary, the questions, and "
            "llms.txt describe both sets of maps."
        ),
    ),
    (
        "Nov. 26",
        (
            "Added a preliminary analysis of where EPA&rsquo;s four real-time lead monitors "
            "sat, compared with the forecast path and with models rerun on NOAA&rsquo;s weather "
            f'analysis (<a href="{ANALYSIS_PATH}">the analysis</a>). The header, the About '
            "box, the summary, the questions, and llms.txt report it. The header also links "
            "EPA&rsquo;s data viewer and the Army&rsquo;s updates. The maps did not change."
        ),
    ),
    (
        "Nov. 25",
        (
            "After the blast: the page now says Middletown&rsquo;s city clerk reported that the "
            "Army, CDC, EPA and FEMA had confirmed normal activities could resume (CBS2 Iowa, "
            "Nov. 25), and the FEMA evacuation is shown as Nov. 24 advice. Text written before "
            "the blast is now in the past tense: what the map shows, how sure it is, the "
            "forecast winds, the release point, the mitigation, and how to cite the map. The "
            "Wednesday to Friday page says the Thursday and Friday runs are for reference, and "
            "its forecast refresh stops. The maps did not change."
        ),
    ),
    (
        "Nov. 25",
        (
            "The &ldquo;When&rdquo; paragraph no longer repeats the planned 9 a.m. time (from "
            "the Army&rsquo;s Nov. 24 advisory and FEMA&rsquo;s alert); the "
            "Army&rsquo;s Nov. 24 advisory is now cited on its evacuation and shelter advice. "
            "The maps did not change."
        ),
    ),
    (
        "Nov. 25",
        (
            "The Army&rsquo;s 3 p.m. update: air sensors report no lead detection, ground "
            "sampling is underway, and people should wait for its all-clear. EPA&rsquo;s "
            "real-time readings through 4 p.m. were all below the 0.18 &micro;g/m&sup3; "
            "detection limit the Army cites; lab and soil and water results are still pending. "
            "The Army&rsquo;s latest maps (191 sq mi above 5 &micro;g/ft&sup2;) replace the "
            "Nov. 24 ones as &ldquo;latest&rdquo;. The maps here did not change."
        ),
    ),
    (
        "Nov. 25",
        (
            "Early air readings: EPA&rsquo;s four real-time lead monitors southwest of the "
            "plant, through 12:20 p.m. CST, with a note that lab results from the other air "
            "samples, and soil and water sampling, are still pending and needed. The maps did "
            "not change."
        ),
    ),
    (
        "Nov. 25",
        (
            "The page now says news outlets report the Army carried out the detonation "
            "Wednesday morning (New York Times, Nov. 25), and to wait for the Army&rsquo;s "
            "official confirmation of the results, which the Army said it would give by 11 a.m. "
            "CST (Army update, Nov. 25). The header, the &ldquo;When was the "
            "detonation?&rdquo; question and the time paragraph now speak of the blast in "
            "the past tense. The maps did not change."
        ),
    ),
    (
        "Nov. 25",
        (
            "The About box is shorter: when, the evacuation zone and FEMA helpline, the "
            "Army&rsquo;s maps, what the map shows, and a clearer warning: it comes with no "
            "warranty, its maker isn&rsquo;t responsible for loss or harm from using it, and it "
            "can&rsquo;t say whether any one place will get lead. The details of "
            "the four cases, the mitigation, the timeline, and news mentions moved here. The "
            "maps did not change."
        ),
    ),
    (
        "Nov. 25",
        (
            "The weather-model spread now uses NOAA&rsquo;s GFS itself: the GFS feed it used "
            "was really HRRR for the first two days, so HRRR was counted twice. ECMWF&rsquo;s "
            "run now uses ECMWF&rsquo;s own mixing height instead of a fixed typical value."
        ),
    ),
    (
        "Nov. 25",
        (
            "The wind at about 250 m above the ground (the 975 hPa level, near the top of the "
            "cloud) is now used. A rule meant to skip levels under the ground left it out, so "
            "the wind between 80 m and about 450 m was a straight-line guess."
        ),
    ),
    (
        "Nov. 25",
        (
            "Maps drawn from the HRRR forecast use its 80 m wind near the ground. The "
            "forecast service has no 120 m wind for HRRR, so until now the wind between "
            "the ground and the lowest pressure level was estimated from the 10 m wind."
        ),
    ),
    (
        "Nov. 25",
        (
            "Added what the Army described at its Nov. 24 news conference: a vent in the "
            "barriers, two walls of water tanks, a foam-filled dam and a screen and foam on the "
            "magazines, and Col. Aaron Teller&rsquo;s account of a 1977 blast with no "
            "mitigation that put about 25% of the lead into the air (Lis 2026; Purpura 2026). "
            "Added a note that moving where the blast starts by 2 or 3 miles changes which "
            "towns are inside the lines more than how far they reach. The maps did not change."
        ),
    ),
    (
        "Nov. 24",
        (
            "FEMA&rsquo;s evacuation zone and helpline are in the page header. Text that said "
            "the Army hadn&rsquo;t disclosed how much lead gets airborne now gives the "
            "Army&rsquo;s estimate, an emission factor of 0.26 with its barriers, water wall, "
            "gel blocks, foam and misters (McFate 2026b; U.S. Army 2026c)."
        ),
    ),
    (
        "Nov. 24",
        (
            "The middle case is now 26% of the lead airborne, labeled &ldquo;U.S. Army "
            "mitigated&rdquo;: the emission factor of 0.26 in "
            "the Army&rsquo;s Nov. 24 &ldquo;Mitigated 0.26&rdquo; plume maps (U.S. Army "
            "2026, Nov. 24 maps), instead of the 20% upper-bound precedent from a Department "
            "of Energy handbook."
        ),
    ),
    (
        "Nov. 24",
        (
            "Maps open on a 9 a.m. blast, the time in the Army&rsquo;s Nov. 24 public safety "
            "advisory and FEMA&rsquo;s emergency alert (McFate 2026b; FEMA 2026). Blast times "
            "are now 8:30, 9:00 and 9:30 a.m. only, so forecast updates go out faster; the 10 "
            "a.m. to 1 p.m. maps were dropped."
        ),
    ),
    (
        "Nov. 24",
        "The cloud now spreads with the forecast&rsquo;s turbulence instead of fixed "
        "stability-class curves. The new method matched measured spread in two tracer "
        "experiments and NOAA&rsquo;s HYSPLIT model better. The cloud is wider: the highest "
        "levels mostly reach less far, and the lowest air level covers a larger area. "
        "Details: " + _a(TURBULENCE_URL, "TURBULENCE.md"),
    ),
    (
        "Nov. 24",
        (
            "Blasts modeled every hour from 9 a.m. to 1 p.m., after the Army said &ldquo;Wednesday "
            "morning&rdquo;; Thursday maps removed."
        ),
    ),
    (
        "Nov. 23",
        (
            "Dry deposition over cropland uses late-autumn values (Zhang et al. 2001); the "
            "weather-model spread also runs each forecast with a revised scheme (Emerson et al. "
            "2020). Source added for the 20% middle case (DOE 1994)."
        ),
    ),
    (
        "Nov. 22",
        "Maps for Wednesday, Nov. 25, the Army&rsquo;s new date, with four forecast models.",
    ),
    ("Nov. 20", "First published."),
]


def changes_html() -> str:
    """Return the change log as an HTML list."""
    items = "".join(f"<li><b>{when}:</b> {what}</li>" for when, what in CHANGES)
    return f'<ul class="changes">{items}</ul>'


def render(ctx: dict[str, Any], site_url: str, built_txt: str) -> str:
    """Return the HTML body of the Methodology and References dialog.

    Parameters
    ----------
    ctx
        Build facts, as for :func:`assumptions`, plus ``models`` (forecast models used).
    site_url
        Address given in the "Citing this map" entry.
    built_txt
        Build time shown as "Last updated".
    """
    refs = "".join(f"<li>{r}</li>" for r in REFERENCES)
    rows = "".join(
        f'<tr><th scope="row">{a}</th><td>{b}</td><td>{c}</td></tr>' for a, b, c in assumptions(ctx)
    )
    today = dt.datetime.now(SITE_TZ).date()
    return f"""
  <p><b>{METHOD_HEAD}</b> {method_intro(ctx["pct"])}</p>
  <p><b>{ANALYSIS_HEAD}</b> {ANALYSIS_METHOD}</p>
  <h3>{CHANGES_HEAD}</h3>
  {changes_html()}
  <h3>References</h3>
  <p class="meta">Sources for the model, data, and assumptions.</p>
  <ul class="refs">{refs}</ul>
  <p class="meta">{data_credits(ctx.get("models", []))}</p>
  <h3>Key assumptions</h3>
  <div class="tablewrap"><table class="assume">
    {ASSUME_HEAD}
    <tbody>{rows}</tbody></table></div>
  <h3>Citing this map</h3>
  <p>Iowa Lead Tracker, 2026: Unofficial estimate of lead dispersal from the 25 November
    2026 detonation at the Iowa Army Ammunition Plant. Interactive map, accessed
    {today.day} {today.strftime("%B %Y")}, {_a(site_url)}.</p>
  <p class="meta">{CONTACT_HTML}</p>
  <p class="meta">Model code: puff_dispersal.py ({_a(SOURCE_URL)}), a Gaussian puff
    screening model. It is not a regulatory or emergency-response model.
    Last updated {html.escape(built_txt)}.</p>"""
