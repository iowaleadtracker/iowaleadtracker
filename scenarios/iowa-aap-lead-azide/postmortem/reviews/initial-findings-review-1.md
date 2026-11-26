# Referee report: "Initial findings from the Nov. 25 detonation at the Iowa Army Ammunition Plant"

Document reviewed: `initial_findings_20261126_0626Z.md` (the "summary"), against the longer
paper `README.md` in the same folder, the data in `data/`, the stored sources in
`data/sources/`, and the sources I could fetch. Review date: Nov. 26, 2026. This is an
automated referee report by an AI model. It is not peer review by a person in the field.

I did not rerun the tracker or HYSPLIT. I recounted the EPA file, read the JSON data behind
every figure in the summary, read each stored PDF, fetched three outside sources, and
extracted weather profiles at the plant from the two weather files in the model work
folder with HYSPLIT's `profile` tool. I changed no file but this one.

## Recommendation: major revision

Nearly every number in the summary matches the data files, and the arithmetic I checked is
right. The problems are in what the numbers are taken to show. Three are serious. First,
every monitor-specific result rests on a source point that the project's own scenario
README says is not the detonation site, and the summary never says so. Second, the ranking
of the four explanations goes beyond the longer paper and beyond the evidence: one "against"
argument is contradicted by the summary's own direction data, and the case against a lofted
cloud rests on one slide bullet and on a "stable layer" that the better of the two weather
files does not show at those heights. Third, the "prior research" paragraph for the
coarse-particle explanation drops the caveats the longer paper carries and uses the
Notre-Dame paper for a point its authors do not make. The summary also drops one required
warning and makes place statements that the repository rules restrict.

## Major concerns

### 1. The source point is not the detonation site, and the summary does not say so

**Sentences.** "AS01 was inside the modeled cloud in every run and read near zero."
"The nearest monitor was placed to catch a cloud of fine dust at the ground. Even 1% of the
lead as fine dust would have read hundreds of times above what it posted." "For 1%, the
window is still 213° to 234°. Every direction estimated here falls inside it." Also the
figure 1 legend: "Detonation site."

**What is wrong.** All distances and bearings are measured from one point,
40.825518, −91.266502. The scenario README says this "is a point for the plant as a whole,
about 400 m from Middletown's centre; it is not the magazines. Their location is not in any
public source (the EPA permit redacts it)." It also says the Army planned to vent the blast
"into three miles of uninhabited area," and concludes that "numbers for single towns within
about 25 mi" do not hold up to the unknown release point. A single monitor 4.5 miles away
is the same case. Neither the summary nor the longer paper mentions this.

**Evidence.** I moved the source and recomputed AS01's position. A 3 km shift puts AS01 at
198° to 245° and 2.6 to 6.0 miles, depending on the direction of the shift. A 2 km shift
gives 207° to 237°. The 1% window in the summary is 21° wide. So a source error the
project already treats as plausible is as large as the whole window. The direction sweep
covers changes in bearing but not in distance, and it was not presented as a test of source
position.

**Suggested rewording.** Add to the opening of section 2: "Every distance and bearing here
is from one point taken for the whole plant. The site of the detonation is not public.
Moving the source 2 miles can move AS01's bearing by up to 25°, as much as the windows
below. Read every statement about AS01 with that in mind." Change "AS01 was inside the
modeled cloud in every run" to "AS01 was inside the modeled cloud in every run from the
assumed source point." Relabel the star in figure 1 "Assumed source point (the plant)."

### 2. The ranking of the four explanations overreaches

**Sentences.** "That leaves four explanations. The two likeliest are that very little fine
lead got out, or that the lead was on particles too coarse for the monitors to measure."
"Four explanations, most to least likely. The order is the author's judgment."

**What is wrong.**

(a) *The summary ranks more than the longer paper does.* The paper (section 6.6) says only
"the first and the fourth are the likeliest" and "the data so far can't choose among them."
It does not rank a lofted cloud above a cloud that passed to the south. The summary's
ordered list does.

(b) *Explanations 1 and 2 are not alternatives about fine lead.* Explanation 2 still needs
"no more than about 0.01% to 0.03%" of the lead finer than the inlet's cut (paper, section
6.6). So under both, almost no fine lead reached AS01 at the ground. They differ on one
thing: whether much coarse lead left the site. Explanation 2 also needs two unconfirmed
things at once: a PM10 or finer inlet, and nearly all airborne lead on coarse particles.
Explanations 3 and 4 are the ones that would allow a large fine release that the monitors
missed. They matter most for exposure and they get the least analysis.

(c) *The case against explanation 3 is thin.* "A Sandia report, not peer reviewed, says the
foam 'suppresses cloud buoyancy' (Frakes 2011)." The source is a 12-slide conference deck.
The words are one bullet in a list of "Benefits." The pictures show a 100 lb charge inside
a 50-foot foam cone. The scenario README works out that the Iowa charge was about 3,800 lb
TNT equivalent, "38 times its van test," and that scaling "would call for roughly 85 ft of
foam" against at least 2 ft on the magazine tops. The summary drops all of that.

(d) *The case for explanation 3 cites the wrong layer, and misses a stronger point.* "The
9 a.m. analysis has a stable layer between about 40 and 240 m." I extracted the 9 a.m.
profile at the plant from both weather files. The pressure-level file has only two levels
there: potential temperature 271.6 K at 43 m and 273.0 K at 241 m. That is stable, and it
is equally stable from 241 to 448 m (274.6 K). The file cannot show where the stable air
starts. The native-level archive, which the paper calls the better input, has constant
potential temperature (272.0 K) from about 30 m to about 150 m, an upward heat flux, and a
boundary-layer height of 261 m at 9 a.m., 424 m at 10 and 673 m at 11. So the air was mixed
to about 150 to 260 m at 9 a.m. and stable above. The models' cloud top is 251 m. That
number is the Church formula for an open-air charge (about 500 m here) cut in half for
earth cover, and MODEL.md calls the half "a screening assumption, not a validated value."
Whether the cloud topped out below or above the boundary layer therefore turns on an
unvalidated factor of two. That is the real argument for explanation 3. It is absent.

(e) *"Prior research: none found for this event type"* is not accurate. The model's own
cloud height comes from published work on detonation cloud rise (Church 1969, as used in
LLNL HotSpot; MODEL.md). That literature is the prior research for explanation 3.

(f) *No lofted-cloud run was made.* The coarse-particle explanation was calculated. The
lofted-cloud explanation was not, though HYSPLIT is set up and a release from, say, 250 to
500 m is one more run.

(g) *"That leaves four explanations" reads as a complete list.* It is not. Missing: the
source was somewhere else (concern 1); the public feed is processed in a way that hides
small values (concern 4); the instruments were not sampling or not reporting lead during
the passage (the layer does not name the substance, and EPA's own instrument list for AS01
to AS04 does not include this instrument, per the paper's section 3.8).

**Suggested rewording.** "Four explanations fit the near-zero reading at AS01. There may be
others, and they can overlap. The data so far can't rank them. Explanations 1 and 2 agree
that almost no fine lead reached AS01 at the ground. They differ on whether much coarse
lead left the site. Explanations 3 and 4 would mean a fine cloud missed the monitors. We
calculated explanation 2. We have not yet calculated explanation 3." Drop "most to least
likely" from the heading. Replace the "For" under explanation 3 with: "The archived weather
has the air mixed to about 150 to 260 m at 9 a.m. and stable above. The models' 251 m cloud
top is half the open-air formula's value, an unvalidated assumption."

### 3. The argument against explanation 4 is contradicted by the direction data

**Sentences.** "*Against:* it can only hide a small release. At 1% of the lead the monitors
respond from 213° to 234°." And in the tests: "For 1%, the window is still 213° to 234°.
Every direction estimated here falls inside it."

**What is wrong.** Explanation 4 has the cloud travel "toward 204° to 211°." That is
outside 213° to 234°. So the window is not an argument against it. The summary also says
"every direction estimated here falls inside" the window, three paragraphs before it gives
an estimated direction that falls outside. The longer paper is careful here: "Only a cloud
that followed the surface wind exactly, toward 204°–211°, would be at the window's edge."

**Evidence** (`data/monitor_coverage.json`, highest hourly mean at any real-time monitor,
µg/m³):

| Cloud heading | Case | Tracker, forecast | Tracker, analyzed | HYSPLIT |
|---|---|---|---|---|
| 204°–205° | 1% | 0 | 0.003 | 0.027 |
| 204°–205° | 7% | 0 | 0.019 | 0.19 |
| 204°–205° | 26% | 0 | 0.07 | 0.70 |
| 208°–209° | 1% | 0.04 | 0.19 | 0.12 |
| 210°–211° | 1% | 0.04 | 0.81 | 0.39 |

At the southern end of the summary's own range, both tracker runs hide the 7% case, and the
forecast run hides any release at all. Only HYSPLIT's wider cloud shows it. Figure 5 shows
this drop inside its gray band, which the summary's caption does not explain. A shallow
cloud would also be narrower than the modeled one, which starts 251 m deep, so the rigid
turn understates how easily it could miss.

Two more limits belong here. The analyzed path (215°) sits 2° inside the 213° edge, and 5°
to 7° inside the analyzed-weather runs' own edges (208° and 210°), while the paper says the
direction "isn't known to better than about 10°." And "nearby surface stations had the wind
from 28° to 31°" is a vector mean of five stations that individually read 355° to 050° at
9 a.m. and 349° to 050° at 10 a.m. (paper, Table 2).

**Suggested rewording.** "*Against:* from about 208° on, it can only hide a small release:
at 1% the runs give 0.04 to 0.8 µg/m³ at the best-placed monitor. *But:* at 204° to 207°
the tracker's cloud misses every monitor even in the 7% case (0 to 0.02 µg/m³); only
HYSPLIT's wider cloud is caught (0.19 to 0.8)." Change "Every direction estimated here falls
inside it" to "The modeled paths (215° on analyzed weather, 229° to 230° forecast) fall
inside it, the first by only 2°. A cloud that followed the surface wind (204° to 211°)
would not." Change the station sentence to "five nearby stations averaged 28° to 31°, but
ranged from 349° to 050°."

### 4. The detection limit: wording, extrapolation, and what a zero means

**Sentence.** "Published limits for this kind of monitor put its noise near 0.009 µg/m³ for
a 5-minute sample (our extrapolation from CARB 2018). So a zero means under about 0.01 to
0.03 µg/m³, not none."

**The table and arithmetic are right.** CARB 2018, Appendix 2 (image on PDF page 44),
lead row: 1.8, 0.63, 0.22, 0.078, 0.042, 0.027 ng/m³ at 15, 30, 60, 120, 180, 240 minutes,
headed "68% Confidence Level (C1σ) per US EPA IO3.3 and Currie." The formula beside it is
σ = √(R·t·I)/(S·t·I) and MDL = σ/V. With volume proportional to time, that gives time to
the power −1.5. The table follows it: 1.8 × (15/t)^1.5 gives 0.636, 0.225, 0.080, 0.043,
0.028. At 5 minutes it gives 1.8 × 3^1.5 = 9.35 ng/m³, or 0.009 µg/m³. Three standard
deviations is 0.028.

**What is wrong.**

- The first clause says published limits put the noise there. They do not. The published
  table stops at 15 minutes (0.0018 µg/m³). The same document says "the sampling time can
  be set in a range between fifteen minutes and four hours." The 5-minute figure is three
  times outside the table, for an operating mode that the document does not describe.
- The scaling assumes the analysis time equals the sampling time, and the same tube
  current and sensitivity. A newer 5-minute mode need not keep any of those.
- The figure is one standard deviation of counting noise on a clean deposit. It is the
  maker's figure, reproduced in a state procedure (the sources README says so). It is not
  a field detection limit. EPA's own test found a blank tape reading "approximately
  1 ng/m3" of lead and an offset of 1.6 ng/m³ (EPA 2012).
- EPA has not said these are Xact 625i units, or that they sample for 5 minutes.
- **The posted readings do not look like noise of that size.** If the noise were 0.009
  with negatives posted as zero, about half the readings would be above zero and about 39
  of 247 would be above 0.009. The file has 17 above zero and 2 above 0.009. Values as
  small as 0.00001 are posted, so there is no simple cutoff near 0.009 either. So either
  the noise is far smaller than the extrapolation, or the feed is processed in a way no one
  has described. Either way the step "so a zero means under about 0.01 to 0.03" does not
  follow. The longer paper's line that "the readings are what the instrument's noise would
  look like" has the same problem.

**Is the extrapolation defensible?** As an order-of-magnitude guess, labeled as one, yes.
As the basis for saying what a posted zero means, no.

**Suggested rewording.** "EPA hasn't published a detection limit. For one monitor of this
kind, the maker's table gives 0.0018 µg/m³ for lead at 15 minutes, the shortest time
listed, as one standard deviation (CARB 2018). If the table's formula held down to
5 minutes it would give about 0.009 µg/m³, or about 0.03 at three standard deviations.
That is our extrapolation below the table's range, not a published value, and the posted
readings are quieter than it implies. Until EPA states the limit and how the feed treats
small values, a posted zero can't be turned into an upper bound."

### 5. The "prior research" for the coarse-particle explanation is not fair to the sources

**Sentence.** "After the Notre-Dame fire, officials reported no air sample over the limit,
and soil sampled later held about a ton of excess lead within 1 km downwind (van Geen et
al. 2020)."

**What is wrong.** Both facts are in the paper. The use is not fair.

- The air result is a health-agency news release of May 9, 24 days after the fire. The
  paper says: "This indicated that Pb exposure through inhalation was unlikely, although
  the timing of the sampling relative to the fire was not provided."
- The paper reports that air monitoring did see the plume: "a twentyfold increase in
  airborne Pb concentrations at a distance of 50 km in the aftermath."
- The paper describes the smoke as "PbO particles entrained with the hot ascending air,"
  which is a fume, not coarse debris.
- The authors put the gap between official findings and the soil down to when and how much
  was sampled: official surface measurements "considerably underestimate the amount of the
  Pb that was actually deposited in the plume area because of their timing." They do not
  mention particle size.
- The longer paper says all of this: "without saying when the samples were taken" and "They
  do not attribute the difference to particle size." It adds: "Neither event was a
  detonation, and neither shows what happened in Iowa." The summary drops all three.

**Lioy et al.** "particles finer than 2.5 µm were under 2% of the mass" is supported
(0.88–1.98%). But it is the size of dust that had settled from a building collapse, by
total mass. The paper analyzed lead in samples "not differentiated by particle size."
Settled dust is the coarse end of what was emitted. It does not show the airborne cloud
was coarse, and it says nothing about what size the lead was on.

**Tremper et al.** "differences put down partly to inlet location." I could not read the
paper. A search-result summary of the abstract gives "a combination of inlet location and
sampling temperature, variable blank levels in filter paper and recovery rates from acid
digestion," and good agreement with filters (median slope 1.07). Inlet location is where
the inlet stood, not its size cut. Placed under the coarse-particle explanation, the
sentence invites the wrong reading. If anything it supports the instrument.

**Aurell et al.** The summary says it is cited from the abstract only and "we have not
extracted its lead figures." The full paper is free on EPA's site and I read it. It is the
closest peer-reviewed evidence to this event and it bears on both leading explanations:
"PM emission factors are significantly higher for soil-covered versus surface detonations
due to the large amounts of soil ejected"; "The PM10/PM2.5 ratio for covered detonations is
approximately 30/1; for open detonation of Comp B, the ratio is about 1/1"; and metals from
the munitions "showed between 0.3% and 22% of the metal transferred to the air emissions
with the majority of the data indicating approximately 1% transferral or less." The
project's own MODEL.md already cites the first finding. The summary files the paper under
explanation 1 and uses none of it.

**Suggested rewording.** "*Prior research:* In field tests of soil-covered detonations,
most airborne particle mass was coarser than 2.5 µm (PM10 to PM2.5 about 30 to 1), and
most data put the share of a munition's metal reaching the air near 1% or less, with a
range of 0.3% to 22% (Aurell et al. 2015). Those were charges of tens of kilograms under
3 to 6 feet of soil, with no water or foam.
In settled World Trade Center dust, particles finer than 2.5 µm were under 2% of the mass
(Lioy et al. 2002); that is settled dust from a collapse, not a detonation cloud. EPA's
2008 lead standard kept total-particle sampling in part because particles too coarse for a
PM10 sampler add to exposure (EPA 2008). After the Notre-Dame fire, soil sampled months
later held about 1 metric ton of excess lead within 1 km downwind; the authors put the gap
with official findings down to the timing and scale of sampling, not particle size (van
Geen et al. 2020). None of these shows what happened in Iowa." Move Tremper to test 4 as
evidence on accuracy, or cut it until the paper is read.

### 6. The analyzed weather is described honestly once, then treated as the truth

**Sentences.** "The forecasts had the right speed and the right general direction."
"Both missed the exact path by the same 10 to 15 degrees." "Speed: the forecasts were
right." "So the miss came from the weather forecast, not from the tracker's math."

**What is right.** "Reading the charts" says the analysis "is not a measurement" and that
"There is no wind instrument at the plant." That is honest. The speed table matches
`snapshots.json` and `army_map.json` in every cell.

**What is wrong.**

- "Right," "missed" and "the exact path" need a known true path. There is none. The summary
  compares forecasts with two model products.
- Those two products disagree with each other by about as much as the "miss." The paper
  says HYSPLIT's path shifts 7° between them. I compared the 10 m wind at the plant grid
  point in both files: they differ by about 3°, 10° and 7° at 9, 10 and 11 a.m.
- A fifth run is left out of the text. HYSPLIT on the pressure-level analyses runs along
  222° to 224°, between the groups. It is drawn in figure 6 as a dashed line inside the
  gray band. The caption says "the lines split into two groups that never cross" and does
  not explain the dashed line. Against that run the forecasts differ by 4° to 8°.
- "The same 10 to 15 degrees" is the top of the range. From `snapshots.json`, at the four
  time marks the tracker's forecast is 8° to 14° from the two reference runs, and the
  Army's air path (227°) is 7° to 13° from them. 15° needs the Army's ground axis (230°)
  against the first-hour 215°.
- I could not confirm that NOAA ARL's archive is a set of analyses. Its surface fields at
  the plant differ from the hourly analyses at every hour I compared, including noon. It
  may hold short forecasts. The summary calls both reruns "the weather as NOAA analyzed it
  afterward." The tracker's rerun uses a third product, Open-Meteo's HRRR as served that
  evening.
- "Reconstruction of each hour afterward" suggests a later reanalysis. The HRRR analysis is
  made in real time each hour from a one-hour forecast and observations (Dowell et al.
  2022).
- "It is the closest thing available to the actual weather" skips the stations, which are
  measurements. They side with the analysis on average but spread over 30° to 60°.
- "Not from the tracker's math" claims too much. Two models agreeing is not validation, and
  the paper has the tracker 1.5 to 1.8 times higher than HYSPLIT in places.

**Is the claim a fair summary of the data?** With softer verbs, yes. Speed: all sources
agree within about 15% at each mark. Direction: the two forecasts lie 7° to 14° west of the two
reference reruns at every mark.

**Suggested rewording.** "The forecasts and the reruns agree on speed and on a
southwesterly path. The reruns on analyzed weather put the path 7° to 14° farther south
than either forecast. The analyzed weather is itself a model product, and its two versions
differ by up to 7° in path, so this is the likely size and sign of the forecast error, not
a measured one." Heading: "Speed: forecasts and reruns agree." And: "So the difference
between the forecast map and the rerun comes from the weather input."

### 7. Repository rules (AGENTS.md): a dropped warning and place statements

- **Dropped warning.** AGENTS.md: "'Don't use it to decide if you're safe' ... must stay
  wherever they appear." The longer paper's banner has "Don't use it to decide if you're
  safe; follow official instructions." The summary's banner has only "Follow official
  instructions." Restore the sentence.
- **Burlington.** "Both maps said southwest, away from Burlington. The weather as later
  analyzed agrees." This tells readers in a named city that the cloud went away from them,
  on model evidence. AGENTS.md: "The site never says a place is safe or unsafe." The longer
  paper does not make this statement. Suggested: "Both maps pointed southwest. The reruns
  on analyzed weather also point southwest."
- **Towns.** "toward Kahoka, Missouri: about 3 miles southeast of West Point and 5 miles
  southeast of Donnellson." These figures are not in the longer paper or the data files. My
  arithmetic gives 2.3 to 3.6 and 3.6 to 5.6 miles for paths of 215° to 221°, so they are
  about right for the assumed source. But the scenario README says numbers for single towns
  within about 25 miles do not survive the unknown release point, and AGENTS.md requires
  the caveat after every list of towns ("A place outside the shaded area may still get
  lead, and a place inside it may get none you could measure"). Add the caveat, or give the
  shift as "about 4 miles at 15 miles out," as the paper does.
- **A health statement without a source.** "Coarse particles are mostly not breathed deep
  into the lungs, but lead on soil and surfaces matters through ingestion, especially for
  children." It sits under "does not show ... unsafe or safe" and the second half keeps it
  from being a verdict. But the first half reassures, and neither half is cited. EPA 2008
  supports the ingestion half ("Pb in all particle sizes contributes to Pb in blood").
  Cite it, and drop or source the first half.
- **Model results stated as facts.** "The nearest monitor was placed to catch a cloud of
  fine dust at the ground" (an inference from model runs and an assumed source; "placed"
  also implies intent). "Even 1% of the lead as fine dust would have read hundreds of times
  above what it posted" (a model value at one grid cell). "Only at about 100 µm ... do they
  fall to the ground first." Suggested: "In every model run from the assumed source, the
  nearest monitor sat inside a ground-level cloud of fine dust. In those runs, 1% of the
  lead as fine dust gives 0.8 to 1.1 µg/m³ there."

## Minor concerns

1. **"Of 244 readings after the detonation, 227 were zero."** The file has 247 readings
   stamped 9:00 a.m. CST or later (230 zeros, 17 not zero) and 244 stamped after 9:00
   (227 zeros). So the sentence is right only if "after" excludes the three stamped 9:00.
   The count in `compare.py` gets 244 another way: it compares the time of day only
   (`t[11:] >= "15:00"`), so it counts the three 9:00 readings as after and the three
   readings from after midnight UTC (AS01 00:01; AS03 00:20, 00:23) as before. The
   per-monitor counts in the paper's Table 6 are wrong for that reason (AS03 has 62, not
   60). Six time stamps appear twice. AS01's two non-zero readings, 9:10 and 9:11, are the
   same value (0.002084) a minute apart and may be one sample. None of this changes the
   picture. Fix the comparison and say "after 9:00 a.m."
2. **"often PM10 (EPA 2012)."** Partly supported. EPA 2012 tested one unit with a PM10
   inlet, and the vendor describes the Xact 625 as measuring "metals in airborne PM10." It
   says nothing about how often. CARB 2018 names "PM2.5 and PM1" in its text and lists
   "PM10, PM2.5, PM1, low volume TSP" as options. A TSP inlet would pass coarse particles.
   Suggested: "The inlet options are PM10, PM2.5, PM1 and total particulate (CARB 2018).
   EPA's own test of the earlier model used PM10 (EPA 2012)."
3. **"EPA's 2008 lead standard keeps all-size sampling because particles larger than 10 µm
   contribute to exposure by ingestion."** Supported (signed rule, pp. 98 and 107; the
   longer paper's two quotations are exact). Three refinements. EPA defines "ultra-coarse"
   as "particles collected by a TSP sampler but not by a PM10 sampler," not as a size.
   "All-size" overstates the method: the rule says the sampler's capture of large particles
   varies, with "a clear risk of underestimating." And the rule allows lead-PM10 monitors
   where levels are low and "sources are not expected to emit ultra-coarse Pb" (p. 256), so
   the longer paper's "EPA does not measure lead against its national air standard with
   PM10 samplers" is too absolute.
4. **Frakes.** The two quotations are exact apart from capital letters ("Suppresses cloud
   buoyancy," "Scrubs particulate material"). It is a conference slide deck, not a
   "technical report" (OSTI lists it as a conference item, authors Klennert and Frakes).
   "Sandia technical reports ... say" is plural with one item cited. "The foam" should be
   "aqueous foam around a 100 lb charge." The slides give no numbers.
5. **"We found no peer-reviewed study" and "samplers flown through the plumes."** Aurell
   used a sampler lofted on a tethered balloon and steered into the plume.
6. **Overlap ranges.** "45% to 66%" and "2% to 14%" match `compare.json` for the 26% case
   (and 2% to 14% also covers the 100% case). The 7% case is left out: 0 to 0.58 between
   the two models and 0 to 0.23 between forecast and rerun. Say which case.
7. **"Its speed was within 0.7 m/s."** True for 9 a.m. to noon (largest 0.69). The longer
   paper's "at every level and hour" is false for the afternoon: up to 1.05 at 3 p.m. and
   2.3 m/s at 5 p.m. (`forecast_vs_analysis.json`).
8. **Explanation 1, "about 0.01% of the lead or less, under a pound."** That uses the
   highest reading at any monitor. The longer paper's floor is "0.01% to 0.03% of the lead,
   one to two pounds." Use one.
9. **"hundreds of times the highest reading."** Arithmetic is right (0.78 to 1.08 against
   0.0021 is about 370 to 520). But it sets an hourly model mean against a reading that is
   in the noise. The paper's "about a hundred times that limit" is the sturdier figure, and
   it too depends on concern 4.
10. **"The Army's own map puts heavy deposits out to 12 miles, which looks like particles
    of a few tens of micrometers."** The map is a forecast for an assumed 26%, not evidence
    of what happened. The paper's own Table 8 gets 10 sq mi and 11 miles from fine
    particles with a faster deposition speed, lists three other explanations, and says "no
    variant here reaches 29 sq mi" and "That is a possibility, not a finding." Suggested:
    "which a coarse share of particles could explain, among other things."
11. **"Only at about 100 µm, the size of fine sand."** The sizes are physical diameters at
    soil density (163 µm aerodynamic); say so. 100 µm is very fine sand. In HYSPLIT, 100 µm
    particles still leave 0.035 µg/m³ at AS01 per 1% of the lead. Particles of 30 µm at the
    lead compound's density also fall out first.
12. **"3 to 7 miles to the side."** I get 3.1, 5.5 and 7.7 miles for AS02 to AS04. "3 to 8"
    is closer. In the HYSPLIT run on pressure-level analyses those monitors are hit (0.91,
    0.42, 0.15 µg/m³ for 7%).
13. **AS01's bearing** is 221° in the monitor file and Table 6 and 222° in the station file
    and the summary.
14. **Figure captions.** Figure 5's gray band (the surface-wind directions) is not
    explained. Figure 6's fifth, dashed series is not explained. Figure 1 does not say the
    Army's zones are placed from the plume's tip.
15. **The 0.18 µg/m³ line.** The Army's map labels it "Lead Air Sampling Method Detection
    Limit" (scenario README). The summary calls it "the Army map's 0.18 µg/m³ line." Say
    what it is.
16. **"EPA's lead monitors."** The public layer does not name the substance (paper, section
    3.8). The summary drops that.
17. **"about a ton."** The paper gives 1.0 metric ton, 95% interval 0.5 to 1.5.
18. **What is peer reviewed.** Lioy, van Geen, Aurell, Tremper, Dowell and Stein are
    journal papers. CARB 2018 is a state operating procedure carrying the maker's table.
    EPA 2012 is a government test report. EPA 2008 is a rule. Frakes is a slide deck. Only
    Frakes is labeled. "Published limits" in test 4 should read "the maker's limits." An AI
    referee's report, including this one, is not the peer review the header says is
    pending.
19. **"Two searches ... could not be run."** Good that it is stated. Say that the missing
    one on cloud rise is the one that bears on explanation 3.

## Source-by-source verification

| Source | Read? | Claim in the summary | Verdict | Evidence |
|---|---|---|---|---|
| CARB 2018, SOP 450 (local PDF) | Yes; Appendix 2 table viewed as an image | Noise "near 0.009 µg/m³ for a 5-minute sample (our extrapolation)" | Partly supported | Pb row: 1.8 / 0.63 / 0.22 / 0.078 / 0.042 / 0.027 ng/m³ at 15 to 240 min, "68% Confidence Level." Formula gives t^−1.5; 1.8 × 3^1.5 = 9.35. Arithmetic right. Table stops at 15 min; text: "between fifteen minutes and four hours." Not a published 5-minute value. See concern 4. |
| CARB 2018 | Yes | "samples through a size-selective inlet" | Supported | §2.3: "a PM size-selective inlet (such as PM2.5 and PM1)"; Appendix 1: "Inlets (PM10, PM2.5, PM1, low volume TSP)." |
| EPA 2012, ETV report (local PDF) | Yes | "often PM10" | Partly supported | "The Xact 625 determines metals in airborne PM10" (vendor's description, "not verified in this evaluation"); figure 3-1 "Xact 625 PM10 inlet." One test. Nothing on "often." |
| EPA 2008, signed rule (local PDF) | Yes, relevant sections | Keeps all-size sampling because particles larger than 10 µm add to exposure by ingestion | Supported, with refinements | p. 98: "ingestion pathways are important to air-related Pb exposures and that Pb particles contributing to these pathways include ultra-coarse particles." p. 107: "use of a Pb-TSP indicator is necessary to provide sufficient public health protection from the range of particle sizes of ambient air Pb, including ultra-coarse particles." p. 256 allows lead-PM10 in limited cases. |
| EPA 2008, response to comments (local PDF) | Text extracted; not used by the summary | None | Not applicable | Background only, per the sources README. |
| van Geen et al. 2020 (local PDF) | Yes, in full | "officials reported no air sample over the limit" | Supported; key context dropped | "no sample collected around the cathedral to assess air quality exceeded the regulatory level of 0.25 µg/m3 ... although the timing of the sampling relative to the fire was not provided." |
| van Geen et al. 2020 | Yes | "about a ton of excess lead within 1 km downwind" | Supported | "integrated excess Pb inventory within a 1 km radius of 1.0 (95% interval, 0.5–1.5) t." Soil collected "9–10 months after the fire." |
| van Geen et al. 2020 | Yes | Used as support for a coarse-particle explanation | Not supported | Authors blame timing and scale of sampling. They report "a twentyfold increase in airborne Pb concentrations at a distance of 50 km" and a PbO smoke. No statement on particle size. |
| Lioy et al. 2002 (archived full-text page; SHA-256 matches the sources README) | Yes | "particles finer than 2.5 µm were under 2% of the mass" | Supported; weak analogy | "Material < 2.5 µm in aerodynamic diameter was 0.88-1.98% of the total mass. The largest mass concentrations were > 53 µm in diameter." Settled dust, total mass; lead not sized. |
| Frakes, SAND2011-3462C (OSTI PDF, 12 slides) | Yes | Foam "scrubs particulate material"; "suppresses cloud buoyancy" | Words exact; weight overstated | Slide 4, "Benefits": "Suppresses cloud buoyancy," "Scrubs particulate material." "Shortcomings": "Must be confined." Slides 5–6: 100 lb charge, 50-foot foam cone. Conference slides, no data. |
| Aurell et al. 2015 (full paper from EPA's site; DOI host blocked) | Yes, in full | "measured particle and metal emissions from open and buried detonations in the field by flying samplers through the plumes" | Supported; relevant findings unused | "aerostat-lofted sampling instrument maneuvered into the plumes"; "buried and metal-cased OD." Findings quoted in concern 5. |
| Tremper et al. 2018 | No. Publisher and DOI hosts blocked. Seen only as a search tool's summary of the abstract | "checked against lab filters, with differences put down partly to inlet location" | Could not verify directly | The search summary matches the sentence and adds sampling temperature, filter blanks and digestion recovery; median slope 1.07. |
| Dowell et al. 2022 | No (not required) | General description of HRRR | Appropriate use | "Afterward" is misleading; see concern 6. |
| Stein et al. 2015 | No (not required) | General description of HYSPLIT | Appropriate use | The paper states the runs are the project's own, not NOAA products. |

## Number-by-number verification

| Figure in the summary | Source value | Verdict |
|---|---|---|
| "about 15 hours after the detonation" | 9:00 a.m. to 12:26 a.m. CST is 15 h 26 min | Supported |
| 244 readings, 227 zero | CSV: 244 after 9:00 (227 zero); 247 at or after 9:00 (230 zero) | Supported if "after" is strict; see minor 1 |
| Highest 0.010 µg/m³ | AS04, 10:00 a.m., 0.010228 | Supported |
| AS01 highest 0.002 µg/m³; every five minutes in the first hour | 0.002084 at 9:10 and 9:11; stamps 9:00, 9:06, 9:10, 9:11, 9:15 ... 10:00 | Supported |
| Monitors 4.5 to 28 miles southwest | 4.5, 12.5, 19.9, 28.1 mi at 221° to 233° | Supported, from the assumed point |
| Speed table, Army map: 6, 27, 43, 79 mi | `army_map.json`: 6.05, 26.78, 42.82, 79.26 | Supported. The map does not say whether a mark is the center or the leading edge (paper, 3.7); the summary drops this |
| Tracker forecast: 6, 31, 48, 85 | `snapshots.json`: 6.41, 30.60, 47.87, 84.92 | Supported |
| Tracker, analyzed: 6, 30, 46, 81 | 6.13, 29.53, 46.35, 81.36 | Supported |
| HYSPLIT, analyzed: 5, 28, 44, 83 | 5.39, 27.71, 44.21, 82.61 | Supported |
| Forecasts along 227° to 231° | Army air path 227.2°, ground axis 230.4°; tracker 228.4° to 231.0° | Supported |
| Analyzed path 215° to 221° | Tracker 214.6° to 219.3°; HYSPLIT 214.6° to 220.3° (snapshots); hourly centers to 220.6° | Supported |
| "the same 10 to 15 degrees" | 8° to 14° (tracker), 7° to 13° (Army air path), 4° to 8° against the pressure-level run | Rounded high; see concern 6 |
| 3 miles southeast of West Point, 5 of Donnellson | Not in the paper or data. My arithmetic: 2.3–3.6 and 3.6–5.6 mi | Roughly right; not found in sources |
| Forecast wind 9 to 18 degrees too far east "all morning" | 10 m, 40 m, 240 m at 9 a.m. to noon: +9° to +18° | Supported |
| Speed within 0.7 m/s | Morning maximum 0.69 | Supported for the morning only |
| Overlap 45% to 66% | 26% case: 0.45, 0.52, 0.66 | Supported for that case |
| Overlap 2% to 14% | 26%: 0.11, 0.14, 0.04; 100%: 0.12, 0.06, 0.02 | Supported for those cases |
| 30 to 40 degrees of arc (7%) | 208°–238°, 208°–240°, 203°–244° | Supported |
| 1% window 213° to 234° | Tracker forecast 213°–234°; analyzed 208°–235°; HYSPLIT 210°–238° | Supported (narrowest run) |
| "Every direction estimated here falls inside it" | 215°, 229°–230° inside; 204°–211° outside | Not supported as written; see concern 3 |
| 0.2% of the lead, 11 to 16 lb, for 0.18 µg/m³ at AS01 | AS01 per 100%: 108.3, 95.8, 78.3 µg/m³; gives 0.17% to 0.23%; 11.5 to 15.9 lb of 6,900 | Supported |
| 1% gives 0.8 to 1.1 µg/m³ | 0.78, 0.96, 1.08 | Supported |
| "hundreds of times the highest reading" | 370 to 520 times AS01's 0.0021 | Supported; see minor 9 |
| 10 and 30 µm reach AS01; about 100 µm falls first | Per 1%: 0.89/1.00; 0.48/0.88; under 0.0001/0.035 (tracker/HYSPLIT) | Supported, with minor 11 |
| Noise near 0.009 µg/m³ at 5 minutes | 1.8 ng/m³ × 3^1.5 = 9.35 ng/m³ | Arithmetic right; an extrapolation; see concern 4 |
| Zero means under 0.01 to 0.03 | One and three standard deviations: 0.0094 and 0.028 | Arithmetic right; inference not supported |
| Fine share "about 0.01% of the lead or less, under a pound" | 0.01 µg/m³ ÷ (0.83 to 0.92 per 1%) = 0.011% to 0.012%; 0.75 to 0.83 lb | Supported; differs from the paper's 0.01%–0.03% floor |
| Army map: heavy deposits out to 12 miles | 11.8 mi from the plume's tip (14.9 from the marker's center) | Supported |
| Under 2% finer than 2.5 µm | 0.88–1.98% | Supported |
| About a ton within 1 km | 1.0 t (0.5–1.5) | Supported |
| Stable layer between about 40 and 240 m | Not in any saved data file. My extraction: true of the pressure-level file; the native-level archive has mixed air to about 150 m and a 261 m boundary layer | Partly supported; see concern 2(d) |
| Farther monitors 3 to 7 miles to the side | 3.1, 5.5, 7.7 mi by my arithmetic | Roughly; "3 to 8" |
| Surface wind toward 204° to 211°; AS01 at 222° | Wind from 24° to 31°; AS01 at 221° or 222° | Supported |
| Stations from 28° to 31° | Speed-weighted vector mean of five: 27.5° and 30.8°; single stations 349° to 050° | Supported as a mean; spread dropped |
| At 0.1% the window is a few degrees | 219°–226°, 227°, 225°–227° | Supported |
| Filter sites AS06, AS12, AS13, AS14, AS18 | Paper, Tables 9 and 12 | Supported |
| Readings as posted through 7:14 p.m. CST | Download 01:14 UTC; last reading 00:23 UTC | Supported |

## What I could not check, and why

- **Tremper et al. 2018.** `amt.copernicus.org` and `doi.org` are not reachable from this
  container. I saw only a search tool's summary of the abstract. I did not read the paper.
- **Dowell et al. 2022 and Stein et al. 2015.** Not read. They are used only as general
  descriptions, which is appropriate.
- **What NOAA ARL's HRRR archive contains** (analyses or short forecasts).
  `www.ready.noaa.gov` reset the connection. My comparison of the two files shows they
  differ. It does not show why.
- **Aurell et al.** Read from EPA's hosted copy
  (`www.epa.gov/sites/default/files/2015-03/documents/9546011.pdf`, SHA-256 `70778999...`),
  not from the journal.
- **The models.** I did not rerun the tracker or HYSPLIT, and did not audit the sweep,
  overlap or snapshot code. I checked the summary against the JSON those scripts wrote.
- **The Army's maps.** I did not retrace the images. Army figures are checked against
  `army_map.json` only.
- **News reports, EPA and Army releases, the vendor slides** cited in the longer paper. Not
  fetched. The summary does not cite them.
- **The stable layer and boundary-layer heights.** My figures come from the weather files
  in the work folder, at the grid point nearest the assumed source. I assume those are the
  files the paper used. Heights for the native levels are my conversions from pressure.
- **EPA's data.** I checked the saved CSV. I could not check it against EPA's viewer, and
  nothing here tests whether the time stamps are UTC, as the paper assumes.
- **The negative claims** ("we found no peer-reviewed study", "none found").
