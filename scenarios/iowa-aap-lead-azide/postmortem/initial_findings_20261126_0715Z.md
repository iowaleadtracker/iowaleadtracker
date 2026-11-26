# Initial findings from the Nov. 25 detonation at the Iowa Army Ammunition Plant (corrected)

**Iowa Lead Tracker (iowaleadtracker.com) · Preliminary analysis, pending peer review**

As of Nov. 26, 2026, 1:15 a.m. CST (07:15 UTC), about 16 hours after the detonation.

> **Unofficial.** This is a screening analysis by a private citizen, not from the Army or
> any government agency. Don't use it to decide if you're safe; follow official
> instructions. The maps and charts are model estimates for assumed releases. They are not
> measurements, and nothing here says how much lead reached any place.

This replaces the [first version](initial_findings_20261126_0626Z.md), written 50 minutes
earlier. An independent review ([report](reviews/initial-findings-review-1.md)) found its
numbers right and several of its conclusions too strong. This version makes those
corrections and adds three tests the review called for. It summarizes the
[first comparison](README.md), which has the methods, data and code. No one outside this
project has reviewed either document; the two reviews so far were by AI referees.

## The short version

- **The forecasts and the reruns agree on speed and on a southwesterly path.** Both the
  Army's map and the tracker's forecast pointed southwest. Reruns of the models on the
  weather as NOAA later analyzed it also point southwest, at the same speed.
- **The reruns put the path 7 to 14 degrees farther south than either forecast.** The
  analyzed weather is itself a model product, so this is the likely size and direction of
  the forecast error, not a measured one.
- **EPA's four real-time monitors posted essentially zero.** Of 253 readings from the
  detonation through 8:40 p.m., 236 were zero and the highest was 0.010 µg/m³. EPA's
  public data doesn't name the substance, the instrument or a detection limit.
- **Whether those monitors were placed to catch a cloud depends on where the detonation
  was, and that is not public.** Measured from one point taken for the whole plant, the
  nearest monitor sits inside the modeled cloud in every run. If the source was 2 km east
  or south of that point, the modeled cloud on analyzed weather passes every real-time
  monitor.
- **Several explanations fit the near-zero readings, and the data can't rank them.** Lab
  results from EPA's filter samplers, and soil and surface samples, are what can.

## 1. Did the weather follow the maps?

We compared five things for the same release. Two are predictions made beforehand. Three
are reruns on NOAA's HRRR weather for the hours of the event.

| Color in the charts | What it is |
|---|---|
| Orange | The tracker's forecast, as shown on the site at 9 a.m. |
| Green | The Army's map, final issue (stamped 7 a.m. Nov. 25) |
| Blue | The tracker rerun on analyzed weather |
| Purple, solid | HYSPLIT on NOAA's archived weather (the reference rerun) |
| Purple, dashed | HYSPLIT on a coarser form of the analyzed weather |

### Speed: forecasts and reruns agree

How far from the assumed source point each one has the center of the cloud, at the four
times marked on the Army's map:

| Time after detonation | Army map | Tracker forecast | Tracker, analyzed weather | HYSPLIT, archived weather |
|---|---|---|---|---|
| 30 minutes | 6 mi | 6 mi | 6 mi | 5 mi |
| 2 hours | 27 mi | 31 mi | 30 mi | 28 mi |
| 3 hours | 43 mi | 48 mi | 46 mi | 44 mi |
| 5 hours | 79 mi | 85 mi | 81 mi | 83 mi |

### Direction: the reruns lie south of both forecasts

The Army's map and the tracker's forecast point along about 227° to 231°. The two
reference reruns point along 215° to 221°, which is 7° to 14° farther south at every time
mark. At 15 miles out that is 2 to 4 miles. The coarser HYSPLIT rerun lies between, at
222° to 224°. The forecast wind near the ground came from 9° to 18° farther east than
NOAA's analysis from 9 a.m. to noon; its speed was within 0.7 m/s in those hours.

These are paths of a modeled cloud from an assumed source point. A place outside a modeled
path may still get lead, and a place inside it may get none you could measure.

![Distance and direction of the cloud at the Army map's four time marks](figures/fig6_time_marks.png)

*Top row: distance at each time. Bottom: direction. The two forecasts (orange, green) run
above the two reference reruns (blue, solid purple). The dashed purple line is HYSPLIT on
the coarser weather file. The gray band is the range of bearings of EPA's four real-time
monitors from the assumed source point.*

![Modeled lead on the ground for the four sources](figures/fig1_ground.png)

*Where lead would settle if 26% became airborne as fine dust. The Army's zones are traced
from its map and placed from the tip of its plume. The star is the assumed source point,
not the detonation site.*

### Reading the charts

- **HRRR** is NOAA's hourly weather model (Dowell et al. 2022). A forecast is what it
  predicted beforehand. An analysis is made each hour, in real time, from a one-hour
  forecast and that hour's observations. It is a model product, not a measurement, and
  there is no wind instrument at the plant. Five surface stations within 16 miles averaged
  a wind from 28° to 31° at 9 and 10 a.m., on the analysis's side of the forecast, but
  individually they ranged from 349° to 050°.
- **HYSPLIT** is NOAA's standard program for working out where something in the air
  travels (Stein et al. 2015). These are our runs of it, not official NOAA products.
- **What the agreement between blue and solid purple shows.** They are two different
  models given much the same weather, and for the 26% case their footprints overlap by
  45% to 66%. The tracker's forecast and rerun footprints overlap by 4% to 14%. So the
  difference between the forecast map and the rerun comes from the weather input. That is
  not a validation of either model: the tracker runs 1.5 to 1.8 times higher than HYSPLIT
  in places, and the two forms of analyzed weather move HYSPLIT's own path by up to 7°.

## 2. Why might EPA's monitors read zero?

**Everything in this section is measured from one point taken for the whole plant
(40.8255° N, 91.2665° W). The site of the detonation is not public.** A shift of 2 km
moves the nearest monitor's bearing by about 15°. Read every statement about a monitor
with that in mind.

EPA's four real-time monitors are 4.5 to 28 miles southwest of that point. The nearest,
AS01, posted a value about every five minutes through the first hour. Its highest was
0.002 µg/m³.

### The tests, in plain English

1. **What if the cloud went a different direction?** We turned the modeled cloud around
   the source point one degree at a time. For the lowest published case (7% of the lead
   airborne) at least one monitor would read 0.18 µg/m³ or more across 30 to 40 degrees of
   arc. That level is the line on the Army's air map, which labels it a sampling method's
   detection limit. For 1%, the window is 213° to 234° in every run. The modeled paths
   fall inside it, the analyzed one (215°) by only 2° to 7°. A cloud that followed the
   surface wind, toward 204° to 211°, is at or past the edge: from 204° to 207° the
   tracker's cloud misses every real-time monitor even at 7%, and only HYSPLIT's wider
   cloud is caught.
2. **How much would the nearest monitor read?** In the model runs from the assumed source,
   1% of the lead as fine dust gives an hourly mean of 0.8 to 1.1 µg/m³ at AS01, roughly
   75 to 105 times the highest value any monitor posted.
3. **What if the source was somewhere else?** We moved the modeled cloud so it starts 1, 2
   and 3 km from the assumed point in 24 directions. On the forecast path the monitors
   catch the 7% case every time. On analyzed weather, with the source 2 km to the east,
   southeast or south, the tracker's cloud misses every real-time monitor in 8 of 24
   directions and HYSPLIT's in 6 of 24, even at 7%. With the source to the north or west
   they still catch it.
4. **What if the particles were coarse?** One particle size at a time: particles of 10 and
   30 µm (at the density of soil) still reach AS01. Only at about 100 µm, or 30 µm for
   particles as dense as the lead compound, does most of the lead fall first. Even then
   HYSPLIT leaves a little in the air at AS01.
5. **What if the cloud rose higher than modeled?** We ran HYSPLIT with the cloud released
   between 251 and 502 m instead of below 251 m. It still reaches AS01 at the ground, at
   6.5 µg/m³ for the 7% case against 5.5, because the morning's mixed layer grows past it
   within the hour and the wind at that height points at AS01. This is one run of one
   model. A cloud that rose well above 500 m could still pass over.
6. **What can the instrument see?** EPA hasn't said. For one monitor of this kind, the
   maker's table gives 0.0018 µg/m³ for lead at 15 minutes, the shortest time listed, as
   one standard deviation (CARB 2018). If its formula held down to 5 minutes it would give
   about 0.009 µg/m³. That is our extrapolation, and the posted readings are quieter than
   it implies. So a posted zero can't be turned into an upper bound. The inlet options
   for this kind of monitor are PM10, PM2.5, PM1 and total particulate (CARB 2018); EPA's
   own test of the earlier model used PM10 (EPA 2012). A PM10 inlet passes little that is
   larger than 10 µm.

![What the best-placed monitor would read as the cloud's direction changes](figures/fig5_monitor_coverage.png)

*Test 1, for the 7% case. The dots mark each run's own direction. The gray band is where a
cloud would go if it followed the surface wind; the tracker's curves fall away inside it.
The dashed lines are 0.18 µg/m³ and the highest value any monitor posted.*

### Explanations that fit, not ranked

They can overlap, and there may be others.

**Almost no fine lead reached the nearest monitor at the ground.** Two versions:

- **Little fine lead became airborne.** The barriers, water and foam worked. In field
  tests of buried and metal-cased detonations of military munitions, most of the data put
  the share of a munition's metal reaching the air near 1% or less, with a range of 0.3%
  to 22% (Aurell et al. 2015). Those tests had no stockpile like this one and no barriers
  like these. Slides from Sandia, not peer reviewed, list "scrubs particulate material"
  among the benefits of aqueous foam around a 100 lb charge (Frakes 2011).
- **The lead was on coarse particles.** It fell before AS01 (test 4) or passed AS01 on
  particles too large for the inlet (test 6). This needs two things EPA hasn't confirmed:
  a PM10 or finer inlet, and nearly all the airborne lead on coarse particles. In the
  same field tests, soil-covered detonations put about 30 times as much particle mass in
  PM10 as in PM2.5, against about 1 to 1 for open detonations (Aurell et al. 2015). EPA's
  2008 lead standard kept total-particle sampling in part because particles too coarse
  for a PM10 sampler add to exposure by ingestion (EPA 2008).

**A cloud of fine lead missed the monitors.** These matter most for exposure. Three
versions:

- **It passed over AS01.** Test 5 argues against this for a cloud up to twice the modeled
  height, in one model. The modeled height itself is half of a published formula's value
  for an open-air charge, an assumption that has not been validated.
- **It passed south of AS01.** A cloud that stayed in the lowest 150 m would follow the
  wind there toward 204° to 211° (test 1). The archived weather has that layer's wind
  from 24° to 31° at 9 a.m. and the wind above it from 51°.
- **The detonation was not at the assumed point** (test 3).

**The public feed doesn't show what the instruments measured.** The data doesn't name the
substance, EPA's list of instruments at these sites doesn't include this kind of monitor,
and the posted values don't behave like raw readings (test 6).

### Two events where air sampling and the ground differed

Neither was a detonation, and neither shows what happened in Iowa.

- In dust that settled after the World Trade Center collapse, particles finer than 2.5 µm
  were under 2% of the mass (Lioy et al. 2002). That is settled dust from a collapse, the
  coarse end of what was in the air.
- After the 2019 Notre-Dame fire, a health agency reported no air sample over the limit,
  without giving the timing. Soil sampled months later held about 1.0 metric ton (0.5 to
  1.5) of excess lead within 1 km downwind. The authors put the gap with official findings
  down to the timing and scale of sampling, not particle size (van Geen et al. 2020).

### What would settle it

- Where the detonation was.
- EPA's lab results from its filter samplers southwest of the plant (sites AS06, AS12,
  AS13, AS14 and AS18 are on the modeled path from the assumed point).
- Soil and wipe samples southwest of the plant.
- The monitors' model, inlet size and detection limit, and how the public feed treats
  small values.
- The Army's balloon data or video showing how high the cloud rose.

As of 1:00 a.m. CST on Nov. 26, none of these was public. EPA's viewer held only the four
real-time monitors and a list of 43 sampling sites.

## What this does not show

- Where lead went, or how much. Every cloud here is a model result for an assumed release
  from an assumed point.
- That either forecast map was confirmed. The reruns agree with them on speed and on a
  southwesterly path, and differ on the path by 7° to 14°.
- That the air was unsafe or safe. Lead in particles of all sizes contributes to lead in
  blood (EPA 2008).

## Limits of this summary

- The literature was not fully searched. Two searches, on detonation mitigation and on how
  high detonation clouds rise, could not be run. The second bears on the cloud-overhead
  explanation.
- Tremper et al. (2018), a field test of this kind of monitor, could not be read and is
  not relied on here.
- NOAA's archived weather may hold short forecasts for some hours, not analyses. We have
  not confirmed which.
- The source-shift and direction tests move or turn the modeled cloud rigidly. They are
  sensitivity tests, not forecasts.
- EPA readings are its preliminary public values as posted through 1:00 a.m. CST on
  Nov. 26.
- This summary was drafted with an AI coding assistant and corrected after a review by an
  AI referee. The maintainer has not yet checked every number by hand.

## Sources

Journal papers:

- Aurell, J., and Coauthors, 2015: Aerostat-based sampling of emissions from open burning
  and open detonation of military ordnance. *J. Hazard. Mater.*, **284**, 108–120,
  doi:10.1016/j.jhazmat.2014.10.029.
- Dowell, D. C., and Coauthors, 2022: The High-Resolution Rapid Refresh (HRRR): An hourly
  updating convection-allowing forecast model. Part I. *Wea. Forecasting*, **37**,
  1371–1395, doi:10.1175/WAF-D-21-0151.1.
- Lioy, P. J., and Coauthors, 2002: Characterization of the dust/smoke aerosol that settled
  east of the World Trade Center (WTC) in lower Manhattan after the collapse of the WTC
  11 September 2001. *Environ. Health Perspect.*, **110**, 703–714.
- Stein, A. F., and Coauthors, 2015: NOAA's HYSPLIT atmospheric transport and dispersion
  modeling system. *Bull. Amer. Meteor. Soc.*, **96**, 2059–2077,
  doi:10.1175/BAMS-D-14-00110.1.
- van Geen, A., Y. Yao, T. Ellis, and A. Gelman, 2020: Fallout of lead over Paris from the
  2019 Notre-Dame cathedral fire. *GeoHealth*, **4**, e2020GH000279,
  doi:10.1029/2020GH000279 ([copy](data/sources/vangeen_2020_geohealth_notre_dame.pdf)).

Government documents and other sources, not peer reviewed:

- CARB, 2018: Standard operating procedure for an Xact 625i ambient metals monitor, CAMB
  SOP 450. California Air Resources Board. A state procedure that reproduces the maker's
  table ([copy](data/sources/carb_2018_sop450_xact625i.pdf)).
- EPA, 2008: National Ambient Air Quality Standards for Lead; final rule. 73 Fed. Reg.
  66964 ([signed version](data/sources/epa_2008_lead_naaqs_final_rule_signed.pdf)).
- EPA, 2012: Environmental Technology Verification report: Xact 625 particulate metals
  monitor. EPA/600/R-12/680. A government test report
  ([copy](data/sources/epa_2012_etv_xact625.pdf)).
- Frakes (with Klennert), 2011: Containment options for IEDs and RDDs using aqueous foam.
  Sandia National Laboratories, SAND2011-3462C, https://www.osti.gov/servlets/purl/1141006.
  Conference slides.
