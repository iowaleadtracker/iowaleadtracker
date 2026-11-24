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
    "Iowa HHS, 2026: Planned lead azide detonation fact sheet&mdash;November 23, 2026. Iowa "
    f"Department of Health and Human Services, {ACCESSED}, "
    + _a("https://hhs.iowa.gov/media/19822/download?inline=")
    + ".",
    "KCCI, 2026: Court records: Army plans to detonate lead azide by Tuesday. KCCI 8 News, "
    "22 November 2026, accessed 22 November 2026, "
    + _a("https://www.kcci.com/article/lead-azide-bomb-detonation-iowa-tuesday/74499570")
    + ".",
    "KCRG, 2026: Trump orders the Army not to detonate bomb-making chemicals in Iowa without "
    "court approval. KCRG-TV9, 23 November 2026, accessed 23 November 2026, "
    + _a("https://www.kcrg.com/2026/11/23/president-trump-orders-military-pause-iowa-detonation/")
    + ".",
    "MACTEC Federal Programs, 2008: Emission factors developed based on Exploding Ordnance "
    "Emission Study Phase II Series 7 testing conducted at Aberdeen Proving Ground, Maryland. "
    "Draft background report, AP-42 5th ed., Chapter 15, U.S. Army Environmental Command and "
    "U.S. EPA, "
    + _a("https://www.epa.gov/sites/default/files/2020-11/documents/b15_eo7_draft_feb08.pdf")
    + ".",
    "McFate, L., 2026: Postponed: Lead azide detonation. U.S. Army Sustainment Command, "
    f"19 November 2026, {ACCESSED}, " + _a("https://www.army.mil/article/296926") + ".",
    "NOAA, 2025: Radar images: Reflectivity. NOAA JetStream, last updated 11 March 2025, "
    "accessed 23 November 2026, " + _a("https://www.noaa.gov/jetstream/reflectivity") + ".",
    (
        "Pasquill, F., 1961: The estimation of the dispersion of windborne material. <i>Meteor. "
        "Mag.</i>, <b>90</b>, 33&ndash;49."
    ),
    (
        "Schiller, L., and A. Naumann, 1933: &Uuml;ber die grundlegenden Berechnungen bei der "
        "Schwerkraftaufbereitung. <i>Z. Ver. Dtsch. Ing.</i>, <b>77</b>, 318&ndash;320."
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
    "U.S. Army, 2026: &ldquo;The controlled detonation at Iowa Army Ammunition Plant is now "
    "scheduled on Wednesday, November 25, 2026&hellip;&rdquo; Post by the U.S. Army on "
    "Facebook, 22 November 2026, accessed 23 November 2026, "
    + _a("https://www.facebook.com/story.php?story_fbid=1611961230959211&id=100064360494281")
    + ".",
    # No permalink was available: the post is pinned on the account, and its text was
    # checked from the maintainer's screenshot (Nov. 23, about 11 p.m. CST).
    "U.S. Army, 2026: &ldquo;&hellip;which will occur this Wednesday morning, as previously "
    "scheduled, based on forecast wind conditions.&rdquo; Pinned post by the Acting Secretary "
    "of the Army (@SecArmy) on X, 23 November 2026, accessed 23 November 2026, "
    + _a("https://x.com/SecArmy")
    + ".",
    "U.S. Army, 2026: Public and media advisory regarding the detonation of lead azide at Iowa "
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
    "gfs_seamless": "NOAA NCEP (GFS)",
    "ncep_hrrr_conus": "NOAA NCEP (HRRR)",
    "ncep_rrfs_conus": "NOAA NCEP (RRFS)",
    "ecmwf_ifs025": "ECMWF (IFS 0.25&deg;)",
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
                "Two equal blasts inside earth-covered magazines, modeled every hour from 9 a.m. "
                "to 1 p.m. (the Army has said only Wednesday morning, with no time)"
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
                f"Low {p['low']}, middle {p['mid']}, high {p['high']}, EPA permit "
                f"{p['permit']} of the lead; the rest stays at the site"
            ),
            (
                "Low: floor from AP-42 "
                "blasting-cap tests (MACTEC 2008). High: TNT-equivalent rule (DOE 1994; Steindler "
                "and "
                "Seefeldt 1980). Middle: 20% of the metal as breathable particles, the "
                "handbook&rsquo;s upper-bound precedent for detonations of nuclear weapon "
                "assemblies (DOE 1994, p. 4-4). EPA permit: the emission factor of 1.00 EPA "
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
                f"{ctx['n_models'][:1].upper() + ctx['n_models'][1:]} forecast models pulled "
                f"{ctx['got_txt']}; "
                f"{html.escape(ctx['shown_model'])} shown; &plusmn;5&deg; direction error around "
                "each"
            ),
            "Open-Meteo (Zippenfenig 2023); 5 &times; 5 grid of points around the plant",
        ),
        (
            "Stability and spread",
            "Pasquill&ndash;Gifford classes from wind, sunlight, and cloud; Briggs rural curves",
            "Pasquill (1961); Gifford (1961); Turner (1970); Briggs (1973)",
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
                "Model limits. The Army hasn&rsquo;t published its mister setup. Runs of the "
                "model&rsquo;s "
                "spray option with guessed setups (528&ndash;26,000 gal/min) caught 0.1&ndash;19% "
                "of the "
                "lead (U.S. Army 2026; Slinn 1984; Seinfeld and Pandis 2016)"
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
        f"and {pct['high']} (high), {pct['mid']} (middle) and {pct['low']} (low), based on "
        "Department of Energy and Army\u2013EPA research. The Army hasn\u2019t said what share it "
        "expects; that is the most important number to check. Every setting and its source is "
        "in the key-assumptions table below."
    )


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
  <h3>References</h3>
  <p class="meta">Sources for the model, data, and assumptions.</p>
  <ul class="refs">{refs}</ul>
  <p class="meta">{data_credits(ctx.get("models", []))}</p>
  <h3>Key assumptions</h3>
  <div class="tablewrap"><table class="assume">
    {ASSUME_HEAD}
    <tbody>{rows}</tbody></table></div>
  <h3>Citing this map</h3>
  <p>Iowa Lead Tracker, 2026: Unofficial estimate of lead dispersal from the planned
    detonation at the Iowa Army Ammunition Plant (25 November 2026, per the Army on
    22 November). Interactive map, accessed
    {today.day} {today.strftime("%B %Y")}, {_a(site_url)}.</p>
  <p class="meta">{CONTACT_HTML}</p>
  <p class="meta">Model code: puff_dispersal.py ({_a(SOURCE_URL)}), a Gaussian puff
    screening model. It is not a regulatory or emergency-response model.
    Last updated {html.escape(built_txt)}.</p>"""
