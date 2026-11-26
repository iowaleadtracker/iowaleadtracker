# Referee report

> **Status: superseded. Kept as a record.** This report reviewed the first draft (commit
> `1fb9452`). Its recommendation, "major revision," and its statement that the draft was
> not publishable apply to that draft, not to the current paper. The second draft was
> written to answer it. The table below says where each major concern was handled.
>
> | Concern | What the first draft did | Where the current paper handles it |
> |---|---|---|
> | M1 | Read the tracker's running 60-minute maximum (`m60`) as an hourly mean | Hourly air now uses the clock-hour mean (`conc`); section 3.6 and `scripts/lib.py` |
> | M2 | Said "the forecast held up" from mismatched hours | Forecast and analysis are matched hour for hour (section 4, Tables 1 and 1b); section 1 says the analysis is a model product, not an independent check |
> | M3 | Drew conclusions from a HYSPLIT run that held 9 a.m. weather fixed | Reference runs use NOAA ARL's archived HRRR for all eight hours with nothing held fixed (section 3.5) |
> | M4 | Compared areas without overlap | Every zone comparison reports overlap (Table 5, section 3.6) |
> | M5 | Measured the Army map from the wrong point with too small an error bar, on an earlier issue | Uses the Army's final maps, anchors at the plume's tip with the marker's center as the alternative, and states the pixel error (sections 3.7 and 7) |
> | M6 | Called particle size the likeliest reason for the Army's larger zone without testing it | Tested in Tables 8 and 11 and presented as one explanation among several (sections 6.6 and 7) |
> | M7 | Stated the event and its time without a source; said no station reported low cloud | The event is sourced to the Army and KCRG and 9:00 a.m. is stated as an assumption (section 2); the cloud statement is corrected |
>
> The minor concerns in section 4 were worked through in the same revision. They have not
> been re-audited one by one against the current text. The paper lists the changes under
> "What changed since the first draft."

**Manuscript:** "Postmortem: the Nov. 25, 2026 detonation at the Iowa Army Ammunition Plant. How the Iowa Lead Tracker's forecast compares with HYSPLIT run on the weather that happened, and with the U.S. Army's own plume map" (first draft, `scenarios/iowa-aap-lead-azide/postmortem/README.md`, branch `claude/fervent-turing-led5z2`, commit `69a1b4a`)

**Date of review:** Nov. 25, 2026

**How I checked.** Three tiers, kept separate throughout:

- **R (recomputed):** from raw outputs with my own code. I wrote an independent reader for HYSPLIT's binary `cdump`, my own decoder for the tracker's map payload, great-circle distances, my own sampling of the converted HRRR analyses with HYSPLIT's `profile` and `vmixing`, my own digitization and georeferencing of the Army images, and nine reruns of the tracker from the saved 8:36 a.m. forecast.
- **D (data files):** checked only against the JSON and CSV files in `postmortem/data/`.
- **U (unchecked):** could not check.

My scratch code and outputs are in `/tmp/claude-0/review/`. I did not use the network and changed nothing in the repository.

## 1. Summary of the submission

The author runs a public Gaussian-puff screening model ("the tracker") that published forecast maps of lead deposition and air concentration for a planned detonation of about 9,700 lb of lead azide. About two hours after the reported event, the manuscript asks three questions:

1. Was the weather forecast behind the 9 a.m. map right?
2. Given the weather that happened, does the tracker agree with HYSPLIT?
3. How do both compare with the Army's "Mitigated 0.26" advisory map?

The evidence is:

- the tracker's maps rebuilt from the forecast pulled at 8:36 a.m.;
- one 8-hour HYSPLIT run on the 9 a.m. HRRR pressure-level analysis held fixed (persistence), plus a 1-hour run on the 9 and 10 a.m. analyses;
- airport, road-weather, radar wind-profile, balloon, one solar and AirNow PM observations;
- two 1200 × 675 JPEGs of the Army's map, dated the morning before.

The manuscript concludes that:

- the forecast "held up";
- HYSPLIT "put the lead where the tracker did", with near-field ground zones agreeing closely;
- the Army's 5 µg/ft² zone agrees with HYSPLIT's;
- the Army's 100 µg/ft² zone is 12 times larger, most likely because the Army's model includes coarse particles.

## 2. Overall assessment and recommendation

**Recommendation: major revision.** The draft is not publishable in its present form, and several of its headline statements should not stay on a public page as written.

What holds up:

- The arithmetic is honest. Nearly every number in Tables 1–6 matches the data files, and I reproduced a large sample from raw outputs with independent code (section 5).
- The persistence weather file is what the manuscript says it is: the 15 UTC analysis repeated, not relabelled forecast data.
- The disclaimer and the Limits section are candid.
- Scripts and data are shared.

What does not hold up is the chain from those numbers to the conclusions:

1. **The tracker's "hourly mean air" is a different quantity.** It is the highest running 60-minute mean in each hour, not a clock-hour mean. Every tracker air number after hour 1 is wrong for the stated purpose, and the cloud-speed comparison changes materially.
2. **The forecast check uses mismatched valid times.** The headline comparison sets a forecast interpolated to 9:30 a.m. against a 9:00 a.m. analysis. Matched in time, the forecast was 9–18° too easterly through the whole release layer at 9 a.m. and 11–15° through 450 m at 10 a.m. The "observations" used to confirm the analysis are ones the analysis assimilates.
3. **The near-field agreement with HYSPLIT is not robust.** It comes from the persistence run. The authors' own 1-hour run on two real analyses, whose deposition numbers are in the data file but not in the text, gives a 100 µg/ft² zone less than half the size and 31% less first-hour deposition. Where areas do match, the zones overlap by less than half.
4. **The Army map is placed with more uncertainty than the result it supports.** The zero point is uncertain by 5–8 miles by the authors' own fit. Depending on the anchor, the Army's 5 µg/ft² zone overlaps HYSPLIT's by anything from zero to half.
5. **The particle-size explanation is asserted, not tested.** The test takes seconds in the authors' own model. I ran it: coarse particles close about half the gap and break the 5 µg/ft² agreement the manuscript cites as support.
6. **Statements about the event go beyond the evidence.** The time, occurrence and amount of the detonation are stated as fact with no cited source, and some sentences could be read as saying where lead did or did not go.

## 3. Major concerns

### M1. The tracker's "hourly mean" air is the running 60-minute maximum (R)

`tracker_stats.py` and `figure.py` read the field `m60`. `dispersal/grid.py` (lines 138–176) defines it as "the highest running 60-minute mean reached during each hour". The clock-hour mean is the field `conc`, which is in the same map payload. Section 2.5, the Table 4 caption, the Figure 1 legend ("Tracker, hour-mean at ground") and the script docstring all call `m60` the hourly mean.

In hour 1 the two fields are the same. From hour 2 on, `m60` is an envelope over roughly two hours of cloud travel. Its integral is 1.7–2.6 times that of `conc`, and its weighted centre lags by about 9–10 miles. The data file shows the symptom: the tracker's hour-2 "peak" is 276.63 µg/m³, identical to hour 1.

Like for like (clock-hour mean, 26% case):

| Quantity | Manuscript or its data file (`m60`) | Recomputed (`conc`) | HYSPLIT |
|---|---|---|---|
| Cloud centre, hour 2 | 12.0 mi | 22.2 mi | 20.5 mi |
| Cloud centre, hour 4 | 48 mi | 57 mi | 50 mi |
| Cloud centre, hour 8 | 122 mi | 131 mi | 101 mi |
| Area ≥ 0.18 µg/m³, hour 4 | 645 sq mi | 440 sq mi | 485 sq mi |
| Area ≥ 0.18 µg/m³, hour 8 | 954 sq mi | 499 sq mi | 1,106 sq mi |
| Peak, hour 2 | 277 µg/m³ | 13.5 µg/m³ | 12.3 µg/m³ |

Consequences:

- Table 4's centre ratios "0.96 / 1.2" become 1.14 / 1.30.
- The tracker's cloud is faster than HYSPLIT's from hour 2 (8–14%), not "after the first few hours", and 30% faster by hour 8, not 20%.
- The tracker centres in Table 6 (48 and 122 mi) are wrong.
- The orange outlines in the right panels of Figures 1 and 2 are not hour means.

**Required:** recompute every tracker air quantity from `conc`, redraw the figures and correct the text.

### M2. "The forecast held up" is not supported; the analysis is not an independent check (R)

**(a) Valid times are mismatched.** Section 3 says the tracker's "hour 1" winds "are valid at 10 a.m." They are not. `puff_dispersal.py::_hours_output` samples the met field at mid-hour, which is a linear interpolation to 9:30 a.m. The saved forecast confirms it: 10 m wind 3.70 m/s from 42° at 15 UTC and 4.61 m/s from 44° at 16 UTC, average 4.15 m/s from 43°. So Table 1 compares a 9:30 forecast with a 9:00 analysis, and Table 1b compares it with a 10:00 analysis. Neither is like for like.

Matching valid times, forecast minus analysis in direction (positive means the forecast is more easterly):

| Level (height above ground) | 9 a.m. | 10 a.m. |
|---|---|---|
| 10 m | +18° | +15° |
| 1000 hPa (about 42 m) | +13° | +13° |
| 975 hPa (about 240 m) | +9° | +15° |
| 950 hPa (about 450 m) | +5° | +11° |
| 925 hPa (about 660 m) | −1° | +5° |
| 900 hPa (about 870 m) | −2° | +4° |

Speeds agree within 0.7 m/s at every level. The forecast values are from `met_cache/map_met_all.json` at `c9f8e59`; the analysis values are my own sampling.

The error was not a "turn by 10 a.m." A bias of the same sign was already present at 9 a.m. through the entire release layer (10–251 m). The phrase "above about 200 m, where the cloud starts" misleads: only the top 50 m of the cloud starts above 200 m. The abstract's "within 1 m/s and 6°" survives only because of the half-hour offset, and its "about 15°" near the ground disagrees with Table 1 (19°). Table 1 also omits the tracker's 80 m level (5.4 m/s from 45°), where the analysis interpolates to about 33°.

The same sign shows without any analysis. Among the stations within 16 miles, the four the manuscript averages give 32° at 9 a.m. and 35° at 10 a.m., against the forecast's 42–44°. All five give 24° and 26°. Fort Madison, the nearest station on the downwind side, reported 010° in four of its six reports between 8:55 and 10:35 a.m., and 020° and 030° in the other two.

**(b) The check is circular.** The HRRR analysis is HRRR's own 1-hour forecast adjusted with METAR, radar wind-profile and radial-velocity, aircraft and balloon data. Verifying an HRRR forecast against it gives a lower bound on the error. "Checking" the analysis against the airport reports and the Davenport radar profile that it assimilates shows little about its accuracy at the plant, where there is no observation. The manuscript lists these inputs in section 2.2 but does not draw the consequence. "Across the region the analysis has no bias" is the expected result of assimilation. The three road stations, which are less likely to be assimilated, show a mean error of +20° at 9 a.m. and +14° at 10 a.m.

**(c) The station comparison cannot resolve the error in question.** METAR winds are 2-minute means reported to 10° and whole knots, mostly one or two reports per station-hour. A mean absolute difference of 8–12° is near that noise floor and the same size as the forecast error being judged. With a scatter of 17° across 21 spatially correlated stations, a regional bias of 5° or more cannot be excluded. A regional mean is also not the quantity of interest: within 16 miles the 9 a.m. errors are −33°, −11°, +24°, −1° and +49°.

**(d) One station is excluded after the fact.** "The stations closest to the plant averaged about 35° at 10 a.m." leaves out the Mount Pleasant road station as "sheltered". It is 4.1 miles from the airport, not 2. Including it gives 26°.

**(e) The radar comparison is selective.** Table 2 omits the 746 m level (32 kt against about 24 kt in the analysis). Of the eight radar levels below 1.05 km, three differ from the analysis by 2.7–4.7 m/s. The radar's own scatter of 5–9 kt (2.6–4.6 m/s) cannot support "within about 1 m/s". The radar is 65 miles away, and the 989 m radar level is compared with the analysis at 875 m.

**(f) Stability is called "plausible" without a check.** The analysis's own profile at 9 a.m. is stably stratified between 43 and 241 m (potential temperature +1.4 K). The 6 a.m. soundings show surface inversions to 180–330 m and a capping inversion near 1.1–1.3 km. None of this is discussed.

**Required:**

- Redo Tables 1 and 1b at matched valid times, including the 42 m and 80 m levels.
- State the HRRR cycle and lead time behind the 8:36 pull.
- Compare the forecast directly with observations.
- Say plainly that the analysis is not independent of either the forecast model or the stations.
- Use data that are less circular: NOAA's RTMA/URMA for surface wind, the Army's on-site balloons if released, aircraft soundings, and the hourly winds at the Lake Sugema monitor. Those winds are already in the AirNow files the authors downloaded (37° and 43° for the two hours), are probably not assimilated, and happen to agree with the forecast direction 40 miles out.
- Replace "The forecast held up" with a quantified statement.

### M3. The persistence run cannot carry the tracker–HYSPLIT conclusions, and the only run on real weather contradicts them (R)

**(a) The second question is not tested.** The tracker was run on an evolving forecast and HYSPLIT on one analysis held for 8 hours, so differences in weather and differences in model are confounded in every row of Tables 4 and 5. The abstract's "Run on the 9 a.m. analysis, HYSPLIT put the lead where the tracker did" hides this.

**(b) The manuscript uses the hours it disqualifies.** Section 2.3 says only "the first hour or two are a fair test". The abstract and discussion rest on later hours:

- 71% of HYSPLIT's 26% 5 µg/ft² zone (99 of 139 sq mi) forms in hours 2–3.
- 93% of the 100% zone forms after hour 1. It is still growing when the run ends (88 to 99 miles between hours 7 and 8), so 907 sq mi and 99 miles are truncated by run length.
- The cloud centres at hours 4 and 8 and the 8-hour deposition totals are all persistence results.
- "148 vs 139 sq mi" against the Army is a persistence result too.

**(c) The two-analysis run contradicts the near-field agreement.** `data/hysplit_0900_two_analyses_1h_zhang.json` holds deposition for the 1-hour run with nothing held. The text quotes only its cloud centre and reach and says it is "the same as the held run". It is not. Recomputed from both `cdump` files:

| First hour | HYSPLIT, 9 a.m. held | HYSPLIT, 9 and 10 a.m. analyses | Tracker |
|---|---|---|---|
| Lead deposited, 100% case | 328 lb | 226 lb | 288 lb |
| Ground ≥ 100 µg/ft², 26% case | 2.35 sq mi, 3.8 mi | 1.04 sq mi, 2.3 mi | 2.2 sq mi, 4.2 mi |
| Ground ≥ 100 µg/ft², 100% case | 13.8 sq mi, 10.5 mi | 5.4 sq mi, 6.1 mi | 14.4 sq mi, 12.7 mi |
| Highest hourly air 2.5–3.5 mi out, 26% case | 92 µg/m³ | 53 µg/m³ | 113 µg/m³ |
| Highest hourly air 4–6 mi out, 26% case | 58 µg/m³ | 26 µg/m³ | 75 µg/m³ |

The tracker rows are its first-hour values too. Its 26% zone is complete after the first hour, and its 100% zone grows only to 14.8 sq mi in hour 2. Aggregating the finer run 2 × 2 to 0.006° gives 1.17 sq mi for the 26% zone, so the grid does not explain the difference.

HYSPLIT's own near-field answer moves by a factor of two when the second analysis is added. That is more than the tracker–HYSPLIT differences the manuscript interprets. On real weather the tracker's 100 µg/ft² zone is about twice HYSPLIT's (26%) and 2.7 times (100%), not "0.96" and "1.0". The claim that HYSPLIT deposits 30% more reverses sign in the first hour.

The parenthetical that the two-analysis run's "peaks are higher … because that run used the finer 0.003° grid" is also wrong in substance. At comparable resolution its peak is 209 µg/m³ against 345.

**(d) "Highest hourly air (hour 1)" is a source-cell artifact.** All three maxima sit 0.2–0.55 mile from the release point, in the first one or two cells. Cell areas differ by a factor of two between the models, and HYSPLIT starts from a line of zero width while the tracker starts with a 63 m spread. From 1.5 to 13 miles the tracker's highest hourly air is 1.2–1.5 times the held run's, not 0.80. Compare arc maxima by distance, or sample both models on one grid as the back-test did.

**(e) Persistence holds the morning boundary layer as well as the wind.** From the mass budget (airborne mass divided by the area integral of ground-level air), HYSPLIT's cloud occupies an effective depth of 360–820 m through hour 6 and then 400–550 m in hours 7–8. The tracker's deepens steadily from 380 to about 1,000 m, 2.5 times HYSPLIT's depth by hour 8. That alone can explain HYSPLIT's larger far zones, larger 8-hour deposition and slower ground-level cloud. The discussion instead attributes the narrower far zones to the tracker's 10-minute crosswind basis ("a known choice") without testing it.

HYSPLIT's own `vmixing` utility, run on the same file at the plant, diagnoses Pasquill class A, friction velocity 0.75 m/s and roughness 0.75 m at 9 a.m. The tracker uses class D, and its documentation gives crop roughness of 0.02 m. If `hycs_std` uses the same values, HYSPLIT's turbulence in this run is two to three times what the tracker assumes, which is a second untested explanation for the wider cloud. The Limits section mentions missing fluxes but not what HYSPLIT diagnosed.

**(f) HYSPLIT's 0.18 µg/m³ outline is in the particle-noise regime.** By my estimate from particle mass, cell volume and transit time, 0.18 µg/m³ in the 26% case corresponds to roughly three to six particle passages per cell per hour. The outline is a speckled field, and the farthest and nearest distances are its extreme values. Smoothing "for display only" changes the hour-1 area from 81 to 107 sq mi.

**(g) Two smaller points on the HYSPLIT setup.**

- The fixed deposition speeds are not "from the back-test's Monday case" or "a different day". They are the tracker's display values at a 5 m/s reference wind and are identical on every day (`_bins_output`). The tracker itself varies them with the hourly wind.
- The 10 µm bin holds 10% of the mass and supplies 68% of HYSPLIT's first-hour deposition. The near field is controlled by the top of the assumed size distribution.

**Required:**

- Run the tracker on the analysed weather, or both models on identical held weather.
- Replace the persistence run with hourly analyses before drawing any conclusion beyond hour 1.
- Report the two-analysis deposition results in the text.
- Report the Emerson run that exists on disk but is not mentioned (293 lb in hour 1 against 226 lb).
- Report what HYSPLIT diagnosed for mixing.
- Withdraw "agree closely" and "within about 20%".

### M4. Equal areas are not agreement in place (R)

The near-field bearings differ by 7° (HYSPLIT 222°, tracker 229°), and the high zones are narrow. On a common grid, intersection over union between tracker and HYSPLIT zones is:

| Zone | 26% case | 100% case |
|---|---|---|
| ≥ 100 µg/ft² | 0.27 | 0.31 |
| ≥ 40 µg/ft² | 0.32 | 0.35 |
| ≥ 5 µg/ft² | 0.48 | 0.53 |

Only 43% of either model's 26% 100 µg/ft² zone lies inside the other's. "2.2 vs 2.3 sq mi" is agreement in size only. That zone is 12 tracker cells: my single-member rerun on a 0.64 km grid gives 1.9 sq mi, so its area is good to about ±15%.

**Required:** report an overlap measure alongside areas, and report the near-field bearing difference in the abstract.

### M5. The Army-map comparison is weaker than presented (R)

**(a) The anchor is uncertain by more than the stated error.** Section 2.4 places the Army's shapes by assuming the centre of the magenta box is the detonation point, while reporting that the authors' own fit through ten cities puts the plant about 8 miles north of it. Either figure is larger than the claimed "±5 miles and ±5°".

My independent fit puts the plant 4.6–5.8 miles north and up to 1.6 miles west of the box centre (leave-one-out range 4.8–6.2 miles north). It uses ten city markers, a Mercator or affine model, and gives residuals of 2–4 px. A rough check against the Iowa–Missouri border gives about 2 miles. My fit is rough in its own right: I read marker pixels by eye from enlarged crops, took city coordinates from memory, and the plant lies at the northern edge of the fitted area.

At 15 miles range, 5–8 miles is 20–30° of bearing. Figure 1 shows the problem directly: the Army's plume begins 3–5 miles west of the star, because its apex is at the west side of the box.

Overlap of the Army's 5 µg/ft² zone with HYSPLIT's, by anchor:

| Anchor | Overlap | Intersection over union |
|---|---|---|
| Box centre (authors) | 0 sq mi | 0.00 |
| Plume apex | 15 sq mi | 0.06 |
| City-fit plant position (mine) | 85 sq mi | 0.41 |
| Authors' own 8-mile offset | 97 sq mi | 0.49 |

The last is as good as the tracker–HYSPLIT overlap. The "10–15°" near-field direction difference and the visual separation in Figure 1 are therefore within placement uncertainty.

**(b) "243–250°" is partly an artifact.** The principal axis of the drawn plume bears 241° and passes 1.8 miles from the box centre. The 250° comes from measuring a near point from an origin off the axis. The abstract's "within about 15°" also disagrees with Table 6 (250° against 230° is 20°).

**(c) Drawn areas cannot be measured from these images.** At 2.5 px per mile with semi-transparent, anti-aliased shapes, my digitized areas run from 93 to 156 sq mi (≥ 5) and from 12 to 54 sq mi (≥ 100) depending on the colour tolerance. Using the printed areas is right. But Table 6 then mixes printed areas with drawn lengths, which are inconsistent with each other under the authors' own thresholds (93 and 12 sq mi drawn).

**(d) The air-map comparison is not like for like, and the like-for-like version says something different.** The Army's air map shows discrete circles growing with distance. That looks like individual model puffs. Which circles belong to "+1 hr" and which to "+4 hr" is the authors' reading, not stated on the map. The "centres" compared are the geometric centre of an area for the Army and a concentration-weighted centre of an hour's mean for the models.

The tracker's own snapshot field (`snap`, end of hour) allows a proper comparison, 26% case, ≥ 0.18 µg/m³:

| Time | Army (from the image) | Tracker snapshot | HYSPLIT hour mean |
|---|---|---|---|
| +1 h | 6–9 mi | 11–17 mi, centre 14 mi | 0–17 mi |
| +4 h | 11–69 mi, centre 42 mi, about 516 sq mi | 55–78 mi, centre 66 mi, 400 sq mi | 35–66 mi, centre 50 mi, 485 sq mi |
| +8 h | 89–108 mi, centre 98 mi, about 130 sq mi | 128–153 mi, centre 140 mi, 506 sq mi | 76–137 mi, centre 102 mi, 1,106 sq mi |

Three things follow:

- The Army's cloud travels at about 60–70% of the tracker's speed from the first hour.
- It has a slow tail at +4 h (near edge at 11 miles against 35–55).
- By +8 h it is a quarter to an eighth of the models' area.

"The Army's cloud moves like HYSPLIT's" rests on a coincidence of centre definitions and on HYSPLIT's persistence hours. The slow, low first-hour transport is direct evidence for explanations other than particle size (M6).

**(e) The map is stale.** It is stamped a/o 24 0630 Nov, about 26 hours before the event. The scenario README says the Army planned updates six hours before and hourly after, and that a later PDF (24 0848) exists. The manuscript has "not checked whether the maps differ". A different forecast can by itself change near-field deposition several-fold through wind speed and stability.

**(f) Figure 2 misleads.** It overlays the Army's 0.26 map on 100% model results without saying so.

**Required:**

- Obtain the PDF, as vector if possible, and the latest pre-event map.
- Anchor the plume at its own apex, or show the result under each defensible anchor with honest error bars.
- Compare snapshots with snapshots.
- Remove the Army overlay from Figure 2 or label it.
- Drop "±5°".

### M6. The particle-size explanation is untested, overstated, and only partly supported when tested (R)

The abstract says the Army's model "must put a share of it in heavier particles". Section 6 calls particle size "the likeliest and the largest" of three candidates with no analysis, and says "this event is the first evidence of how much that matters". The event supplied no evidence on particle size. Two pre-event model maps differ. No literature is cited for the claim that the mitigation "would make a lot of larger, wet, soil-bound particles".

The test listed under Next steps takes about four seconds per run. I ran it with the code at `c9f8e59`, the saved 8:36 forecast, HRRR only, 26% airborne:

| Run | ≥ 100 µg/ft²: area, reach | ≥ 5 µg/ft²: area, reach | Lead deposited within 15 mi |
|---|---|---|---|
| Baseline (all "fume" sizes) | 1.9 sq mi, 4.4 mi | 90 sq mi, 35 mi | 78 lb |
| `--size-preset mixed` (1–30 µm) | 10.6 sq mi, 10.6 mi | 187 sq mi, 46 mi | 580 lb |
| `--size-preset soil-bound` (10–100 µm) | 14.5 sq mi, 12.6 mi | 253 sq mi, 52 mi | 995 lb |
| 50% fume, 50% coarse | 12.5 sq mi, 11.5 mi | 174 sq mi, 44 mi | 748 lb |
| Fine sizes, deposition speed +1 cm/s | 9.8 sq mi, 10.6 mi | 314 sq mi, 63 mi | 219 lb |
| Fine sizes, cloud top 50–100 m | 3.2–3.4 sq mi, 6.2 mi | 71–76 sq mi, 31–32 mi | 101–115 lb |
| Fine sizes, Emerson deposition | 2.8 sq mi, 5.0 mi | 128 sq mi, 41 mi | 99 lb |
| **Army map** | **27 sq mi, about 15 mi** | **148 sq mi, about 38 mi** | not given |

The baseline reproduces the published 243 lb and 90 sq mi.

What this shows:

- The direction of the hypothesis is right. Coarse particles enlarge the 100 µg/ft² zone five- to eight-fold.
- Even an all-coarse release reaches only about half of 27 sq mi.
- A faster deposition speed for fine particles does nearly as much. "Likeliest and largest" is not established.
- Every variant that enlarges the 100 µg/ft² zone five-fold or more also inflates the 5 µg/ft² zone to 174–314 sq mi. That removes the "5 µg/ft² zone agrees" result the manuscript presents as corroboration ("a faint far field the same size as ours … made by the fine fraction"). The argument is also not self-consistent on mass: if part of the 26% is coarse, less than 26% is fine, and the fine-only 5 µg/ft² zone must be smaller than the tracker's.
- The Army's ratio of 5 to 100 µg/ft² area is 5.5. The tracker gives 41, HYSPLIT 59, and the coarse variants 14–18. No variant reproduces that shape.

Alternatives the manuscript does not rule out:

- The Army's contours may not be a mean deposition field. Hazard-prediction tools can plot exceedance-probability or conservative-percentile areas.
- A different source term: release height, initial cloud size, lead mass, or deposition reported as compound rather than lead.
- A different, day-old forecast.
- A different averaging or accumulation period.
- A different deposition scheme, or wet removal by the water and foam.
- A lower, slower cloud, which the Army's own +1 h position supports.

**Required:** present particle size as one hypothesis among several, report the sensitivity runs, and remove "must", "likeliest" and "first evidence".

"The 5 µg/ft² zone agrees" should also be withdrawn or heavily qualified. The tracker's own zone is 90 sq mi against 148. Only HYSPLIT's persistence-hours number is close. With the authors' placement the Army's and HYSPLIT's zones do not overlap at all.

### M7. Statements about the event, and public-safety framing

**Not established by anything cited.** That the detonation occurred, that it occurred at 9:00 a.m., that all 9,700 lb detonated, and that the release lasted 6 minutes. The abstract says "News reports say" and "its map gives 9 a.m. CST" (a planned time), and no news report is in the references. The draft then treats 9:00 as fact:

- "about two hours after the detonation";
- "merged at 9:19 a.m., after the detonation";
- "pulled 24 minutes before the detonation";
- the figure titles;
- the word "Postmortem";
- "the weather that happened".

A start 20–60 minutes later would change which analysis applies and every hour label.

**Sentences a resident could misread.**

- "HYSPLIT put the lead where the tracker did"; "both send it southwest … past West Point and Donnellson". This states where lead went and names towns with none of the caveat the project's own rules require after any list of towns.
- "For the public the practical point is narrow … Its yellow (5 µg/ft²) zone was about the right size and in about the right place." "Right" here means "similar to a persistence HYSPLIT run and to a day-old Army forecast". It contradicts section 5 (zero overlap as drawn) and section 6's own "the lead near the plant went more to the south-southwest than the published map showed", which is the direction of Fort Madison. Someone outside the yellow zone could take this as confirmation that they are outside the affected area.
- "If that lasted, the lead … went more to the south-southwest". Conditional, but it asserts movement of lead.
- "an ordinary background with no jump at 9 a.m." leads the particle-monitor paragraph and is quotable as "nothing detected". The qualifications come later and are incomplete:
  - Lake Sugema at 257° is not "between the models' 230° and the Army map's 243–250°". It is outside both: 27° (about 19 miles at that range) from the models' axis and north of the Army's cloud as the authors draw it.
  - The raw AirNow files show it reported no PM2.5 before the 10–11 a.m. hour, so it has no baseline that day.
  - Lead at the Army's 0.18 µg/m³ line is about 2% of the PM2.5 background. A null reading means nothing.
  - "No monitor within 40 miles" sits beside a monitor at 39.7 miles.
- "Hourly air ≥ 32 µg/m³ (DOE PAC-1): farthest 8.7 mi" and similar distances need a statement that they are model output on forecast weather, not a boundary.
- "The forecast held up" as the abstract's first finding.

**A factual error in the weather narrative (D).** "Every station reported no clouds below 12,000 ft except a few at 3,700 ft at Ottumwa" is contradicted by the authors' own `asos_region_20261125.csv`. Fairfield, 41 miles away, reported overcast at 3,100 ft from 8:55 to 9:55 a.m. Oskaloosa reported broken or overcast cloud at 3,800 ft from 7:35 to 9:15 a.m. Muscatine, Iowa City, Washington and Kirksville also reported low cloud during the morning, and Ottumwa was broken at 7:53.

**Required:**

- Cite the source for the event and time, and carry the uncertainty through.
- Remove or rewrite the sentences above.
- Put limitations before findings in the monitor paragraph.
- Do not characterize any zone as "right".

## 4. Minor concerns

1. **Abstract.** "Near the ground the analysis was about 15° more northerly": Table 1 gives 19°, Table 1b gives 14°.
2. **Table 4, ratios.** The 100 µg/ft² area ratio is 0.93 (2.19 ÷ 2.35), not 0.96; the quoted ratio was computed from rounded values. The same applies to 0.96 for the hour-4 centre (0.95, and moot after M1).
3. **Section 4, "within 20% … in both cases".** The 26% 40 µg/ft² reach ratio is 1.23, and the 100% 100 µg/ft² zone extends to 11–13 miles, beyond "about 10 miles".
4. **Section 4, direction.** "Both models send the lead southwest along about 230°": HYSPLIT's near field is 221–222° (far-end bearings of its 100 and 40 µg/ft² zones, and its hour-1 centre).
5. **Table 3, station positions and one blank.**
   - Mount Pleasant airport is 15 miles west-northwest (303°), not "17 mi NW".
   - Fort Madison is at 196° (south-southwest).
   - Ottumwa is at 287° (west-northwest).
   - Ottumwa is marked "not sampled", but the CSV has it (6.3 kt from 43°).
6. **Section 3, surface text.** "North-northeast to northeast winds of 7–13 kt": the table includes 6 kt and 010° (north), and the 13 kt is the 9:53 report.
7. **Table 3b.** The 10 a.m. mean absolute error is 8.6° from the CSV (rounds to 9°, not 8°).
8. **Section 3, sunshine.** Open-Meteo's `shortwave_radiation` is a preceding-hour mean. The forecast for 9–10 a.m. is 259 W/m². The 187 W/m² is the tracker's interpolation of 115 and 259. "As sunny as the forecast's sunshine" should read "as the value the model used". Crawfordsville is 28 miles north-northwest, and whether its timestamps mark the start or end of the hour should be stated.
9. **Section 3, soundings and distances.**
   - "Winds from 65–95° in the lowest kilometer": the files show 15–110° (Lincoln 15° at the surface, 45–50° at 70–130 m, 110° at 1,040 m; Davenport 55° at the surface).
   - The sounding sites are 65 and 111 miles away, not "70–130".
   - The radar is 65 miles away, not 70.
10. **Table 2.** State the height mismatch in the last row, and give the 9:55 a.m. profile as well. It is in the data file.
11. **Section 3, Cantril.** "The Cantril road station on the cloud's path": it is at 254°, 24° off the models' axis.
12. **Section 2.3, source geometry.** "Two vertical lines": the CONTROL file defines one vertical line source by two points. HYSPLIT's zero-width line differs from the tracker's five layers with a 63 m initial spread, and this should be noted.
13. **Section 1 and section 6, back-test citations.**
    - "0.8–1.9×" is in `TURBULENCE.md`, not the back-test README the sentence links to (which says 0.7–1.6× for the prototype).
    - "A low bias in the lowest [zone]" is not a back-test finding. `TURBULENCE.md` says the test "says little about" the 5 µg/ft² zone.
14. **Status and Limits.** Both say one hour of analysed weather was used; sections 3 and 4 use two.
15. **Section 2.1, what the site showed.** At 9:00 a.m. `main` was at `fd17b63` (merged 8:56), not `c9f8e59`. The comparison uses a rebuild, not the deployed files. Say whether the two were compared.
16. **Section 2.1 and 2.2, weather inputs.**
    - State that the tracker's wind field is 25 points about 185 km apart, bilinearly interpolated, against HYSPLIT's 3 km grid.
    - Give the HRRR cycle and lead time behind the pull.
    - "The best gridded estimate" overstates an HRRR initial state. NOAA's RTMA/URMA is the purpose-built surface analysis.
17. **Section 2.5, like-for-like details.**
    - HYSPLIT's 0–10 m layer against the tracker's ground value is reasonable here: I find the 0–10 m and 10–100 m layers within 1–2% of each other through hour 5.
    - State the grid sizes: 0.47 km² tracker cells against 0.23 km² HYSPLIT cells.
    - State the tracker's 8-bit logarithmic packing, with steps of about 8.5%.
18. **Thresholds.** 5, 40 and 100 µg/ft², 0.18 µg/m³ and PAC-1 at 32 µg/m³ are used without references or a statement of what they mean outdoors.
19. **Figures.**
    - The hour-8 outlines of both models run off the bottom and left of the right-hand panels.
    - "Hannibal" is hidden under the legend.
    - HYSPLIT's 100 µg/ft² outline is barely visible.
    - Three line styles in three colours are hard to separate.
    - Add a scale in miles and state lines.
    - The right-panel title says "at about +1, +4 and +8 hours" for fields that are hour means, and the caption does not say the Army shapes are snapshots.
20. **Reproducing.** The section is not sufficient to reproduce the results.
    - There is no script for the persistence file (prose only).
    - There is no script for the Army measurements and city fit behind Table 6 and section 2.4, the radar decode, the analysis sampling behind Tables 1, 1b and 2, the Table 3b summary, the AirNow extraction, or the Monday check.
    - `station_vs_hrrr.py` expects `asos_region.csv`, `rwis.csv` and `net_*.geojson`. The first two are under different names in `data/obs/`, and the station lists are not in the repository.
    - `figure.py` silently depends on files `hysplit_stats.py` writes into the run directory and hardcodes the release hour.
    - `hysplit_stats.py` deletes files in the run directory.
    - `data/` is described as "observations as downloaded", but several files are derived.
    - Package versions are not given.
21. **References.**
    - Benjamin et al. (2016), Dowell et al. (2022), Stein et al. (2015) and Zhang et al. (2001) are real and correctly cited as far as I can tell from memory. I did not check them online. Stein et al. lacks its DOI (10.1175/BAMS-D-14-00110.1).
    - I could not confirm McFate (2026), the Army map images ("supplied by the maintainer"; provenance and resolution should be stated), or the bucket and URL citations. They are plausible.
    - Missing: any source for the detonation itself; the EPA permit; the DOE PAC database; EPA dust-lead levels; Emerson et al. (2020) if that run is reported; any literature on particle sizes from detonations, which the central hypothesis needs.

## 5. Verification table

R = recomputed independently from raw outputs; D = checked against data files only; U = could not check.

| Item (location) | Claimed | My value | Tier | Status |
|---|---|---|---|---|
| Lead released, 26% and 100% (Tables 4–5) | about 1,800 and 6,900 lb | 1,794 and 6,901 lb | R | OK |
| Tracker ground ≥ 100, 40, 5 µg/ft², 26% (Table 4, abstract) | 2.2 sq mi / 4.2 mi; 9.1 / 9.6; 90 / 35 | 2.19 / 4.18; 9.13 / 9.63; 90.3 / 34.9 | R | OK |
| Tracker ground zones, 100% (Table 5) | 15 / 13; 39 / 23; 479 / 75 | 14.8 / 13.3; 38.5 / 23.3; 478.5 / 75.6 | R | OK |
| Tracker lead on ground after 8 h | 243 and 936 lb | 243.3 and 935.9 lb | R | OK |
| HYSPLIT ground zones, 26% | 2.3 / 3.8; 8.0 / 7.8; 139 / 37 | 2.35 / 3.78; 8.04 / 7.84; 139.1 / 37.4 | R | OK |
| HYSPLIT ground zones, 100% | 15 / 11; 59 / 24; 907 / 99 | 14.6 / 11.1; 58.5 / 24.1; 906.6 / 99.7 | R | OK, but the 5 µg/ft² zone is still growing at 8 h |
| HYSPLIT lead on ground after 8 h | 312 and 1,200 lb | 312.1 and 1,200.5 lb; mass budget in MESSAGE gives 1,201 lb | R | OK |
| Highest hourly air, hour 1 | 277 and 345 µg/m³ (1,064 and 1,328) | 276.6 and 345.2 (1,064 and 1,328) | R | OK numerically; source-cell artifact (M3d) |
| PAC-1 farthest, 26% and 100% | 8.7 vs 6.1 mi; 23 vs 22 mi | 8.71 vs 6.11; 22.7 vs 21.8 | R | OK |
| Air ≥ 0.18, hour 1, farthest | 17 and 17 mi | 16.7 and 16.9 mi | R | OK |
| Direction of 5 µg/ft² far end | 231° and 230° | 231.6° and 229.8° | R | OK |
| Tracker cloud centre, hours 4 and 8 (Tables 4 and 6) | 48 and 122 mi | 47.6 and 121.6 mi from `m60`; **57.1 and 130.8 mi from the hourly mean** | R | **Wrong quantity** |
| HYSPLIT cloud centre, hours 4 and 8 | 50 and 101 mi | 49.9 and 100.8 mi | R | OK |
| Centre ratios (Table 4) | 0.96 / 1.2 | 1.14 / 1.30 like for like | R | **Mismatch** |
| "Tracker about 20% faster after the first few hours" (abstract) | 20% | 8–14% from hours 2–4, 30% at hour 8 | R | **Mismatch** |
| Ratio, 100 µg/ft² area (Table 4) | 0.96 | 0.93 | R | Mismatch (rounding) |
| "HYSPLIT deposits about 30% more" | 30% | 28% over 8 h held; **−21%** in hour 1 on two analyses | R | Not robust |
| Two-analysis run: centre, reach, peak (section 4) | 6.0 mi at 222°; 19 mi; 589 µg/m³ | 5.96 mi at 221.9°; 19.3 mi; 588.7 µg/m³ | R | OK; deposition results omitted (M3c) |
| Monday check (section 2.3) | 597 lb; 24, 14, 9 µg/m³ | 596.6 lb; 23.8, 14.0, 9.1 µg/m³ | R | OK |
| Persistence file is the 15 UTC analysis repeated | yes | sampled records identical in all 9 frames; differs from the forecast file | R | OK |
| Table 1, analysis at 9 a.m. | 3.7 m/s from 24°; 7.2 / 48°; 8.3 / 55°; 9.3 / 60°; 10.5 / 65° | 3.7 / 24–25°; 7.1 / 48°; 8.3 / 55°; 9.3 / 59°; 10.5 / 65° | R | OK |
| Table 1b, analysis at 10 a.m. | 5.0 / 29°; 7.2 / 35°; 8.7 / 46°; 9.6 / 55°; 10.3 / 61° | 4.9 / 29°; 7.2 / 35°; 8.8 / 46°; 9.7 / 55°; 10.3 / 61° | R | OK |
| Tables 1 and 1b, tracker column | 4.2 / 43°; 7.5 / 54°; 8.4 / 58°; 9.9 / 59°; 10.5 / 64° | same, from the map payload; it is the 9:30 interpolation | R | OK numerically; **valid time misdescribed** |
| "Hour 1 winds are valid at 10 a.m." (section 3) | 10 a.m. | mid-hour, 9:30 a.m. | R | **Wrong** |
| Table 2, analysis at the radar | 7.8 / 062°; 10.2 / 074°; 12.0 / 081°; 12.9 / 082° | 7.8 / 62°; 10.2 / 74°; 12.0 / 81°; 12.9 / 83° | R | OK |
| Table 2, radar column | as printed | matches `kdvn_vad_20261125.txt`; the 746 m level is omitted | D | OK, selective |
| Table 3, observations | as printed | match the METAR file | D | OK |
| Table 3, analysis at stations | 7 kt / 017°; 8 / 034°; 8 / 044° | 6.9 / 17°; 8.1 / 34°; 7.6 / 45° | R | OK |
| Table 3, Mount Pleasant position | 17 mi NW | 15.3 mi at 303° | R | Mismatch |
| Table 3b | +3°, 0°, 12°, +0.2 kt; +2°, 0°, 8°, 0.0 kt | +3.1°, 0°, 12.0°, +0.16 kt; +1.8°, 0°, 8.6°, +0.03 kt | D | OK except 8° should be 9° |
| "Stations closest … averaged about 35°" | 35° | 35.3° for four stations; 26° with the fifth | D | Selective |
| Road station "2 miles" from the airport | 2 mi | 4.1 mi | R | Mismatch |
| Sky report (section 3) | no cloud below 12,000 ft except Ottumwa | Fairfield overcast at 3,100 ft and others | D | **Wrong** |
| Sunshine | 187 W/m² forecast; 686 kJ/m² (about 190 W/m²) | 187 is interpolated (forecast 259 for the hour); 686.16 kJ/m² is 190.6 W/m² | D | Convention issue |
| Mixing height and class | about 440 m rising to about 950 m, class D | 438 to 975 m (945 at hour 8), D | D | OK |
| AirNow PM2.5 range, 5–10 a.m. | 4–12 µg/m³ | 4.0–12 µg/m³ | D | OK |
| Lake Sugema position | 40 mi at 257°, "between" 230° and 243–250° | 39.7 mi at 257°; outside both | R | **Wrong inference** |
| Lake Sugema first reading | 8 µg/m³, 10–11 a.m. | 8 µg/m³; no earlier PM2.5 in the raw files | R | OK; no baseline |
| Army printed areas | 27 and 148 sq mi | as printed on the image | R | OK |
| Army 5 µg/ft² far end | about 38 mi, 243° | 37.9 mi at 243° from the box centre; 35 mi at 241° from the apex | R | OK given the anchor |
| Army 100 µg/ft² far end | about 15 mi | about 16 mi from the box centre, 12–13 mi from the apex (read from an enlarged crop) | R | Roughly OK |
| Army air blobs (Table 6) | 6–9 mi at about 250°; 11–69 mi, centre 42, about 240°; 89–108 mi, centre 98, about 228° | 6–9 mi at 253°; 11–69 mi, 42 at 240°; 89–108 mi, 98 at 228° | R | OK as measured; interpretation is not (M5d) |
| Plant relative to the box centre | about 8 mi north | 4.6–5.8 mi north (my fit) | R | Differs; either exceeds ±5 mi |
| "±5 mi and ±5°" | stated | not supported | R | **Unsupported** |
| "About 12 times"; "15 sq mi, about half" | 12×; 15 | 12.3× and 11.5×; 14.8 and 14.6 | R | OK |
| Commit times | 8:55 and 9:19 a.m. | 08:55:02 and 09:19:32 CST | R | OK |
| Scaling by 0.26 is exact | stated | linear; yes | R | OK |
| HRRR file posting times; conversion from GRIB | 9:54 and 10:53 a.m. | not checked (I used the converted file) | U | – |
| Radar decode from Level III | – | not redone | U | – |
| Whether the 0848 PDF differs from the 0630 images | "not checked" | not checked | U | – |
| That the detonation occurred at 9:00 a.m. with 9,700 lb | stated | no source in hand | U | **Not established** |
| References online | – | not checked (no network use) | U | – |

## 6. Writing and presentation

The prose is plain and mostly clear, and the units are handled carefully. Several habits make it read as templated, not as a scientist working through evidence:

- **Verdict-first bold lead-ins on nearly every paragraph.** "**Winds aloft: yes.**", "**The analysis aloft matches the radar.**", "**Across the region the analysis has no bias.**", "**Direction and the near field agree.**" Each announces a conclusion before the evidence, and several are stronger than the paragraph beneath. Use neutral run-in heads ("Winds aloft.") or none, and let the numbers lead.
- **Question-then-verdict.** "Was the weather forecast right? … The forecast held up." A careful writer would give the size and sign of the error.
- **Repeated "X, not Y" constructions.** "It answers 'where would the lead go if the 9 a.m. weather lasted,' not 'where did it go'" appears twice (sections 2.3 and 8). "It isn't an observation", "a reference model, not the truth" and "not how much lead it carried" are the same move. Once is enough.
- **Triads and tidy closers.** "bigger particles, faster deposition, or a cloud that starts lower"; "Neither says what was actually deposited; only sampling can."; "For the public the practical point is narrow."; "They answer different questions."
- **Pre-emptive explanation in place of evidence.** "which fits a snapshot", "which suggests a sheltered sensor", "High cloud likely explains the gap". Each is a guess that reads as a finding.
- **"We" throughout** a document whose header says it is run by "a private citizen". Say who did the work.
- **The abstract carries too many numbers** and the wrong emphasis. It should lead with what cannot yet be said.
- **The title** claims "HYSPLIT run on the weather that happened". For seven of eight hours it was not.
- **"Postmortem"** implies established outcomes. "Preliminary comparison" would be accurate.

Structure: move Limits ahead of Results, or fold each limit into the section it qualifies. Put the Army-map method and its uncertainty before any Army number. Give Tables 1 and 1b a single matched-time form.

## 7. Most important fixes, in priority order

1. **Remove or rewrite the public-facing claims now:**
   - "The forecast held up";
   - "HYSPLIT put the lead where the tracker did";
   - the "practical point" paragraph ("about the right size and in about the right place");
   - the named towns without the caveat;
   - the particle-monitor lead sentence and the "between" statement about Lake Sugema;
   - the sky-cover sentence.

   Cite the source for the event and its time, and stop treating 9:00 a.m. as established.
2. **Fix the tracker air quantity** (`conc`, not `m60`) and recompute Table 4's centre and air rows, Table 6, the right-hand panels of both figures, and the speed statements.
3. **Redo the forecast check at matched valid times** and state the result: 9–18° too easterly in the release layer at 9 a.m., 11–15° through 450 m at 10 a.m., speeds within 0.7 m/s. Say that the analysis is neither independent of the model nor of the stations used to check it.
4. **Stop drawing conclusions from persistence hours.** Report the two-analysis run's deposition (226 lb against 328 lb; a 100 µg/ft² zone of 1.0 sq mi against 2.35). Replace the 8-hour run with hourly analyses. Run the tracker on the same weather. Report what HYSPLIT diagnosed for mixing.
5. **Report overlap, not only area,** for every zone comparison.
6. **Rebuild the Army comparison:** a better source image and the latest pre-event map; an anchor consistent with the plume's own apex and honest error bars; snapshot against snapshot; no "±5°"; no 0.26 overlay on the 100% figure.
7. **Recast the particle-size section** as one hypothesis among several and include the sensitivity runs. Coarse presets give 10.6–14.5 sq mi and inflate the 5 µg/ft² zone. A faster deposition speed gives 9.8 sq mi. A lower cloud gives 3.3 sq mi. None reaches 27 sq mi or the Army's area ratio.
8. **Correct the smaller mismatches** in section 4 above, complete the references, and make the Reproducing section runnable end to end from the repository.
