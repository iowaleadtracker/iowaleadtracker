# HYSPLIT back-test, November 2026

A comparison of this model against NOAA's HYSPLIT for the same release on four past
afternoons and evenings, using archived weather. It was run on Nov. 24, 2026, to check
how far the published maps could be off and in which direction. **Nothing here changes
the site or the model.** The model variants below were tried in a scratch copy only.

**The production method and the final comparison tables are in
[`TURBULENCE.md`](../../TURBULENCE.md)** (`--spread turbulence`, with a 10-minute
crosswind basis). This folder keeps the back-test's setup, HYSPLIT inputs and the earlier
prototype variants it was developed from; numbers here are from the scratch prototype.

This is an unofficial comparison. HYSPLIT is a widely used reference model, not the
truth, and its results here are not official NOAA or government material.

## Summary

- **The cloud's path matches in daytime.** On the three daytime days the airborne center
  stays within about 5° and a few miles of HYSPLIT's, hour by hour. In the stable evening
  it does not: ours heads 20–30° farther west and travels farther (53 vs 43 mi after
  5 hours).
- **The first hour matches** within about 20% (peak hourly air near the plant: ours
  815 / 849 / 586 / 1,429 µg/m³ against HYSPLIT's 0–10 m 1,000 / 801 / 636 / 1,742 on the
  overcast, sunny, windy and evening cases).
- **After the first hour, the current model runs high in daytime neutral air** (stability
  class D, overcast or windy): about 2–5× HYSPLIT for peak air, the distance where hourly
  air exceeds DOE PAC-1, and the ground zones. In sunny, unstable air (classes B–C) it is
  closer, about 1–2×.
- **The main cause is crosswind spread.** After 5 hours of an overcast afternoon, HYSPLIT's
  cloud was about 3× wider than ours (crosswind standard deviation about 10 km against
  3 km). The Briggs rural curves the model uses were fitted to short-period sampling and
  grow the cloud too slowly over hours. Our cloud also stays closer to the ground than
  HYSPLIT's well-mixed daytime layer.
- **HYSPLIT's 0–100 m layer average is not the cause in daytime.** There its 0–10 m
  layer is only 1.2–2× its 0–100 m average. In the stable evening it is 3–5×, so in stable
  air a 0–100 m average would understate what people breathe; all comparisons here use
  HYSPLIT's 0–10 m layer.
- **In stable evening air (class F) the current model underpredicts peak air.** Distances
  are 1.2–1.8× HYSPLIT's, but peak hourly air at hours 2–3 is about half of HYSPLIT's:
  HYSPLIT keeps the lead in a thin, concentrated layer near the ground. This matters for
  maps that run into the evening.
- **Widening the cloud at a fixed rate overcorrects in stable air.** A Heffter-style
  crosswind growth (0.5 m/s), with or without doubled vertical growth, brought the daytime
  cases to 1.0–2.0× HYSPLIT but cut stable-evening peak air to a tenth of HYSPLIT's.
  Applying it only in classes A–D keeps every daytime result at or above HYSPLIT and
  leaves stable air as it is now.
- **A turbulence-based spread tracks HYSPLIT on all four cases** (see "Turbulence-based
  prototype"): growth set by the crosswind and vertical turbulence (σv, σw), estimated
  from the weather by the published AERMOD/CALPUFF methods, instead of stability classes.
  Distances came within 0.7–1.6× of HYSPLIT on every case, including the stable evening,
  and first-hour peaks within about 25%. Later daytime peaks ran 0.4–0.7× HYSPLIT's, so it
  is no longer always on the cautious side.
- **Field data say stable-night plumes are narrow filaments that swing widely.** Project
  Sagebrush Phase 2 found night plumes covering 50–150° of arc, as wide as by day, but
  made of narrow filaments with concentrations one to two orders of magnitude above
  daytime ones (see "Literature"). One map cannot show both; a narrow cloud plus a wide
  direction-uncertainty view at night would.
- **The deposition scheme moves the ground zones a lot but not the air.** Emerson et al.
  (2020) instead of Zhang et al. (2001) changed the ground zones by up to about 50% and
  deposited about a third more lead, but did not change the ratios to HYSPLIT. HYSPLIT's
  own particle deposition scheme deposited about 4.5× more lead than HYSPLIT with our
  deposition speeds (Monday only).

- **Measured tracer data agree.** Against Project Sagebrush Phase 1 (169 measured σy, 200
  to 3,200 m) the current Briggs curves are about 2× too narrow (0.55×), AERMOD 0.66×, and
  the turbulence prototype 1.11× with 99% within a factor of 2. Against Prairie Grass the
  prototype is 1.45× (1.02× scaled to its 10-minute samples), AERMOD 0.97×, Briggs 0.78×.
- **For Wednesday's forecast the prototype would shrink the far zones 3–6×** (100% case:
  air above PAC-1 from 56 to 8 mi; ground ≥100 µg/ft² from 24 to 6 mi) but bring
  Middletown, next to the plant, into the 100 µg/ft² zone.

Not yet done: a direction-uncertainty view sized by the turbulence and wind speed at night,
the prototype as reviewed code with updated tests, more days (including the blast day once
its HRRR weather is archived), and the real-weather validation checks.

## Method

**Release (both models).** The site's EPA permit case: 9,700 lb of lead azide, 1.64 MJ/kg,
two charges, earth-covered (cloud top 251 m), 100% of the lead (3,130 kg) airborne in the
`fume` sizes (0.3, 1, 3 and 10 µm at 9,500 kg/m³), at the plant (40.825518, −91.266502).
Five hours from the release. Our model used the site's settings (`make_map_picker.py`
`MODEL_ARGS`: `--land-use crops`, `--dt 60`, `--grid 360`) with `--release-case
permit-100 --hours 5 --extent-km 120 --weather-model ncep_hrrr_conus`, at commit
`f3b69b7` (the model physics are unchanged at `0e3e11d`).

**Days.** Chosen for different weather at the plant (HRRR, first hour):

| Case | Release (CST) | Weather | Stability class | Boundary layer |
|---|---|---|---|---|
| Overcast | Mon Nov 23, noon | NW 4–5.5 m/s, overcast | D | about 750 m |
| Sunny | Thu Nov 19, noon | SW about 5 m/s, clear | B–C | 670–950 m |
| Windy | Sun Nov 22, noon | NW 7.6–8.3 m/s, clouds clearing | D | about 900 m |
| Stable evening | Thu Nov 19, 6 p.m. | S–SE about 2 m/s, clear | F | about 50 m |

**Weather.** Our model: Open-Meteo's HRRR (`ncep_hrrr_conus`, forecast API, which serves
recent past days) on the usual 5×5 grid. HYSPLIT: NOAA ARL's archived HRRR in ARL format
(`https://www.ready.noaa.gov/data/archives/hrrr/`, files `20261123_18-23_hrrr`,
`20261119_18-23_hrrr`, `20261122_18-23_hrrr`, `20261120_00-05_hrrr`; 3.4 GB each), on its
full 3 km grid.

**HYSPLIT.** Version 5.4.2, public (unregistered) Ubuntu 20.04 build, `hycs_std`, 3D
particles, 200,000 particles (`inputs/SETUP.CFG`). The inputs (`inputs/*.CONTROL`) were
written by `puff_dispersal.py --hysplit`, then changed by hand:

- the weather file name and directory (the export writes a GDAS1 name);
- output levels `0 10 100`, so HYSPLIT reports deposition (level 0) and air in the 0–10 m
  and 0–100 m layers;
- a fixed dry deposition velocity per particle size, taken from our model's map for that
  run (the speeds it reports at its reference wind of about 5 m/s): Zhang
  0.16 / 0.10 / 0.32 / 3.66 cm/s, Emerson 0.11 / 0.26 / 0.73 / 3.91 cm/s for 0.3 / 1 / 3 /
  10 µm. Our model varies these with the wind each hour, so the match is approximate,
  most of all on the windy day.

To rerun one, put its HRRR file next to the `CONTROL` file (renamed to `CONTROL`),
with `SETUP.CFG` and HYSPLIT's `bdyfiles` (`ASCDATA.CFG`, `LANDUSE.ASC`, `ROUGLEN.ASC`),
and run `hycs_std`. Each run took about 10 minutes on one CPU.

**Comparison.** HYSPLIT's packed `cdump` was read, summed over the four particle sizes,
and sampled at each of our map's cells (about 0.67 km). Air is the highest hourly mean on
the map: ours at ground level, HYSPLIT in its 0–10 m layer. Distances are the farthest
cell from the plant at or above the level; deposition is after 5 hours. On the windy day
the cloud leaves the 120 km test map by hour 5, so later hours and the farthest zones
there are cut off for both models.

**Model variants (scratch only, not in the repository).**

- *Heffter + vertical ×2:* the crosswind sigma never falls below 0.5 m per second of
  travel time, a long-range growth rate after Heffter (1965), and the Briggs vertical
  coefficient is doubled as a crude stand-in for faster daytime mixing.
- *Gated (A–D only):* the same, applied only to puffs in stability classes A–D.
- A Turner-style averaging-time correction (crosswind sigma × (60/10)^0.2 ≈ 1.43) was
  also tried on the overcast day: it narrowed the gap only slightly (air above PAC-1 from
  43 to 39 mi).

The Heffter rate and the averaging-time exponent are as commonly quoted; they were not
checked against the original papers for this test.

## Results

"Peak air" is the highest hourly mean on the map in hours 2, 3 and 5 after the release
(µg/m³). "Air ≥ PAC-1" is the farthest point where an hourly mean reached 32 µg/m³.
Ground zones are lead on the ground after 5 hours.

### Overcast, Mon Nov 23, noon (class D)

| Run | Peak air h2 / h3 / h5 | Air ≥ PAC-1 | Ground ≥100 / ≥40 µg/ft² | Lead deposited |
|---|---|---|---|---|
| Current, Zhang | 125 / 60 / 23 | 43 mi | 24 / 44 mi | 923 lb |
| Current, Emerson | 115 / 60 / 21 | 42 mi | 29 / 48 mi | 1,221 lb |
| Heffter + vertical ×2, Zhang | 41 / 17 / 6 | 19 mi | 12 / 21 mi | 724 lb |
| Heffter + vertical ×2, Emerson | 41 / 15 / 6 | 19 mi | 14 / 25 mi | 953 lb |
| **HYSPLIT, Zhang speeds** | 21 / 13 / 9 | 12 mi | 5.9 / 14 mi | 595 lb |
| **HYSPLIT, Emerson speeds** | 20 / 13 / 7 | 11 mi | 8.0 / 15 mi | 778 lb |

On this day HYSPLIT was also run with settling only (420 lb deposited; ground ≥100 / ≥40
µg/ft² at 5 / 11 mi) and with its own particle deposition scheme (2,667 lb deposited;
27 / 46 mi; air ≥ PAC-1 at 10 mi), on the site's finer map grid.

### Sunny, Thu Nov 19, noon (classes B–C)

| Run | Peak air h2 / h3 / h5 | Air ≥ PAC-1 | Ground ≥100 / ≥40 µg/ft² | Lead deposited |
|---|---|---|---|---|
| Current, Zhang | 25 / 17 / 13 | 14 mi | 5.3 / 21 mi | 643 lb |
| Current, Emerson | 23 / 16 / 12 | 14 mi | 7.6 / 31 mi | 844 lb |
| Heffter + vertical ×2, Zhang | 25 / 12 / 5 | 13 mi | 5.3 / 20 mi | 632 lb |
| Heffter + vertical ×2, Emerson | 25 / 12 / 5 | 13 mi | 7.0 / 26 mi | 828 lb |
| **HYSPLIT, Zhang speeds** | 15 / 8 / 9 | 8.2 mi | 5.3 / 11 mi | 677 lb |
| **HYSPLIT, Emerson speeds** | 14 / 8 / 9 | 8.8 mi | 6.2 / 17 mi | 886 lb |

### Windy, Sun Nov 22, noon (class D)

| Run | Peak air h2 / h3 / h5 | Air ≥ PAC-1 | Ground ≥100 / ≥40 µg/ft² | Lead deposited |
|---|---|---|---|---|
| Current, Zhang | 37 / 18 / 0 | 31 mi | 20 / 88 mi | 1,078 lb |
| Current, Emerson | 37 / 16 / 0 | 30 mi | 25 / 88 mi | 1,361 lb |
| Heffter + vertical ×2, Zhang | 17 / 7 / 0 | 17 mi | 13 / 24 mi | 771 lb |
| Heffter + vertical ×2, Emerson | 17 / 7 / 0 | 17 mi | 16 / 29 mi | 964 lb |
| **HYSPLIT, Zhang speeds** | 15 / 8 / 1 | 14 mi | 11 / 16 mi | 507 lb |
| **HYSPLIT, Emerson speeds** | 15 / 8 / 1 | 15 mi | 12 / 20 mi | 662 lb |

### Stable evening, Thu Nov 19, 6 p.m. (class F)

| Run | Peak air h2 / h3 / h5 | Air ≥ PAC-1 | Ground ≥100 / ≥40 µg/ft² | Lead deposited |
|---|---|---|---|---|
| Current, Zhang | 420 / 237 / 146 | 77 mi | 33 / 44 mi | 1,236 lb |
| Current, Emerson | 418 / 236 / 133 | 70 mi | 33 / 53 mi | 1,435 lb |
| Heffter + vertical ×2, Zhang | 88 / 36 / 13 | 27 mi | 16 / 32 mi | 1,333 lb |
| Heffter + vertical ×2, Emerson | 87 / 33 / 11 | 26 mi | 21 / 33 mi | 1,585 lb |
| **HYSPLIT, Zhang speeds** | 554 / 495 / 97 | 45 mi | 23 / 38 mi | 1,662 lb |
| **HYSPLIT, Emerson speeds** | 622 / 544 / 106 | 39 mi | 26 / 40 mi | 2,377 lb |

The gated variant (A–D only) gives the Heffter + vertical ×2 results on the three daytime
days and the current results on the stable evening, which was class F throughout.

### Ours divided by HYSPLIT (same deposition speeds, Zhang)

| Case | Run | Air ≥ PAC-1 | Ground ≥100 | Ground ≥40 | Peak air h3 |
|---|---|---|---|---|---|
| Overcast | Current | 3.7× | 4.1× | 3.2× | 4.6× |
| Overcast | Heffter + vertical ×2 (and gated) | 1.7× | 2.0× | 1.5× | 1.3× |
| Sunny | Current | 1.7× | 1.0× | 1.9× | 2.2× |
| Sunny | Heffter + vertical ×2 (and gated) | 1.6× | 1.0× | 1.8× | 1.5× |
| Windy | Current | 2.2× | 1.9× | 5.4× | 2.3× |
| Windy | Heffter + vertical ×2 (and gated) | 1.2× | 1.2× | 1.5× | 1.0× |
| Stable evening | Current (and gated) | 1.7× | 1.4× | 1.2× | 0.5× |
| Stable evening | Heffter + vertical ×2 | 0.6× | 0.7× | 0.8× | 0.1× |

With Emerson speeds in both models the ratios are within about 0.1–0.5 of these, except
the windy day's current ≥40 µg/ft² ratio (4.3×, clipped by the map edge).

### Heffter crosswind growth alone

Run because CALPUFF switches every puff to Heffter's linear growth once it is 550 m wide,
whatever the stability. Ours ÷ HYSPLIT (Zhang): overcast 2.2 / 2.7 / 1.9 / 1.7×, sunny
1.7 / 1.0 / 1.9 / 1.6×, windy 1.7 / 1.8 / 1.9 / 1.3×, stable evening 0.6 / 0.7 / 0.9 /
**0.1×** (air ≥ PAC-1 / ground ≥100 / ground ≥40 / peak air h3). The fixed 0.5 m/s growth
rate, not the doubled vertical growth, is what fails in stable air.

## Literature

How established models and field experiments handle crosswind spread. Formulas are as
printed in the cited documents (read Nov. 24, 2026).

**Models.**

| Model | Crosswind spread | Crosswind turbulence σv | Minimum σv | Long range / meander |
|---|---|---|---|---|
| This model | Briggs rural curves by stability class, σy = c x (1 + 0.0001 x)^−½ (class D c = 0.08) | not used | – | – |
| CALPUFF `MDISP=2` | σy = σv t fy, Draxler fy = [1 + 0.9 (t/1000 s)^½]^−1 (Eqs. 2-39, 2-65) | similarity: daytime σv = [4u\*² e^(−1.8z/h) + 0.35w\*²]^½; stable σv = u\*[1.6Cs z/L + 1.8 e^(−0.9z/h)]/(1 + z/L), Cs = (1 − z/h)^¾ (Eqs. 2-52 to 2-64) | 0.5 m/s, all classes | Heffter (σy ∝ t) once σy reaches 550 m (SYTDEP) |
| CALPUFF `MDISP=3` (regulatory default) | Pasquill–Gifford tables; σy × (t/60 min)^0.2 for averaging time | – | – | same switch |
| AERMOD (EPA-454/B-26-003, July 2026) | σy = σv x / [u (1 + 78X)^0.3], X = σv x/(u zi), for a near-surface release (Eqs. 77–78) | σv² = 3.6u\*² + 0.35w\*² (Eqs. 38–41) | 0.2 m/s | coherent and random (meandering) plumes weighted by σr²/σh², time scale 24 h (Eqs. 71–73) |
| HYSPLIT (ARL-224) | particles: Langevin, horizontal Lagrangian time scale 10,800 s, so spread grows about linearly with time for hours; puffs: dσh/dt = σu (Eqs. 56–58, 80) | stable v′² = 4.5u\*²(1 − z/zi)^1.5, unstable v′² = 0.36w\*² (Kantha and Clayson; Eqs. 61–72) | – | horizontal deformation diffusivity (Eq. 51) |
| SCIPUFF / HPAC | second-order closure; also predicts concentration variance | boundary-layer profiles | not found | separate mesoscale "large-scale variability" inputs |

u\*, L and w\* come from routine data by AERMET's methods: net radiation from cloud cover
and sun (Holtslag and van Ulden), H = 0.9Rn/(1 + 1/Bo), Monin–Obukhov iteration by day;
θ\* = 0.09(1 − 0.5n²) and the Venkatram u\* quadratic at night (AERMOD formulation Sec. 3).

**Field evaluations.**

- *Irwin (1983)*, 11 tracer sites: Draxler's turbulence-based scheme gave "the smallest
  mean fractional error" and beat Pasquill–Gifford at Prairie Grass and Karlsruhe.
- *Project Sagebrush Phase 1* (Finn et al. 2016; daytime continuous releases, arcs 200 to
  3,200 m): σy "consistently high by a factor of ~2" relative to the Pasquill–Gifford,
  Markee and Briggs curves for classes B–D beyond about 400 m, larger also than AERMOD's
  scheme; averaging time (10–60 min) mattered little; Prairie Grass σθ "likely to be
  unrealistically low, especially at nighttime in low wind speed conditions."
- *Project Sagebrush Phase 2* (NOAA Tech. Memo, 2016 tests; Finn et al. manuscript on
  wind-direction changes): night tests with 1.5 m releases and arcs at 100–400 m, winds
  about 1 m/s, classes E–F. Plumes "often subtended 100–150 degrees of arc" (IOP 5) and
  "50–100 degrees" (IOP 7), "much larger than that suggested by the measured σθ";
  "comparable to daytime". But night concentrations peaked one to two orders of magnitude
  above daytime ones, the tracer staying in one place for more than 10 minutes, then
  shifting tens to over 100 degrees within 10 minutes. Large direction shifts were
  "largely restricted to near surface wind speeds less than 1.5 m s-1". Concentration
  "is best represented by a probability distribution, and one with fat tails."
- *EPA CALPUFF tracer evaluation* (Paumier and Brode 1998; Savannah River, Great Plains,
  INEL): turbulence-based and Pasquill–Gifford options both within a factor of 2 at
  about 100 km with no clear winner; at 600 km σy was 2.5–3.5× too large, mostly from an
  unresolved night-time low-level jet; Pasquill–Gifford's vertical growth produced
  spurious secondary maxima.

## Turbulence-based prototype

Scratch only, not in the repository. Each step, every puff's growth is set by turbulence
at its height instead of by stability class:

1. u\*, L and w\* from the 10 m wind, measured shortwave radiation, cloud cover and mixing
   height, by AERMET's methods (albedo 0.2, Bowen ratio 1.0, 280 K assumed; roughness
   0.02 m for crops).
2. σv and σw from CALPUFF's `MDISP=2` formulas, with CALPUFF's σw minimums by class and a
   σv minimum of 0.2 m/s (AERMOD) or 0.5 m/s (CALPUFF).
3. Growth by Draxler's travel-time functions (fy as above; fz = [1 + 0.9 (t/500)^½]^−1 by
   day, [1 + 0.945 (t/100)^0.806]^−1 when stable), advanced by the virtual-time method;
   once σy passes 550 m, linear growth at σv (CALPUFF's switch, at the turbulence rate
   instead of Heffter's fixed one).

Typical values: overcast noon u\* 0.35 m/s, L −53 m, w\* 1.1 m/s, σv 0.9 m/s; clear night
u\* 0.06 m/s, L 5 m, σv at the 0.2 m/s floor.

| Case | Run | Peak air h2 / h3 / h5 | Air ≥ PAC-1 | Ground ≥100 / ≥40 µg/ft² | Lead deposited |
|---|---|---|---|---|---|
| Overcast | Turbulence, σv ≥ 0.2 | 21 / 8 / 3 | 12 mi | 8.3 / 15 mi | 687 lb |
| Overcast | **HYSPLIT** | 21 / 13 / 9 | 12 mi | 5.9 / 14 mi | 595 lb |
| Sunny | Turbulence, σv ≥ 0.2 | 13 / 5 / 2 | 10 mi | 6.5 / 12 mi | 658 lb |
| Sunny | **HYSPLIT** | 15 / 8 / 9 | 8.2 mi | 5.3 / 11 mi | 677 lb |
| Windy | Turbulence, σv ≥ 0.2 | 7 / 3 / 0 | 9.9 mi | 8.5 / 14 mi | 734 lb |
| Windy | **HYSPLIT** | 15 / 8 / 1 | 14 mi | 11 / 16 mi | 507 lb |
| Stable evening | Turbulence, σv ≥ 0.2 | 594 / 309 / 84 | 48 mi | 38 / 40 mi | 1,123 lb |
| Stable evening | Turbulence, σv ≥ 0.5 | 162 / 48 / 15 | 27 mi | 25 / 35 mi | 1,124 lb |
| Stable evening | **HYSPLIT** | 554 / 495 / 97 | 45 mi | 23 / 38 mi | 1,662 lb |

The daytime cases do not depend on the σv minimum (σv is 0.9–1.2 m/s). First-hour peaks
were 752 / 963 / 543 / 1,458 µg/m³ against HYSPLIT's 1,000 / 801 / 636 / 1,742.

Ours ÷ HYSPLIT (air ≥ PAC-1 / ground ≥100 / ground ≥40 / peak air h3), σv ≥ 0.2: overcast
1.1 / 1.4 / 1.1 / 0.6×, sunny 1.2 / 1.2 / 1.1 / 0.7×, windy 0.7 / 0.8 / 0.9 / 0.4×, stable
evening 1.0 / 1.6 / 1.1 / 0.6×.

**Reading it against the field data.** In daytime the prototype is close to HYSPLIT, whose
horizontal spread also grows about linearly with time. At night the two σv minimums bracket
what Sagebrush Phase 2 measured: 0.2 m/s gives a narrow, concentrated filament like the
observed night peaks; 0.5 m/s spreads the lead over a wider area like the observed arcs.
A narrow cloud for concentrations, plus a direction-uncertainty view that widens at night
and in winds below about 1.5 m/s, would represent both. The site's fixed ±5° view is far
narrower than the 50–150° night arcs measured at Sagebrush.

## Measured tracer data

The crosswind spread σy of each scheme against measured σy, given each test's measured
meteorology. Numbers are the geometric mean of predicted ÷ measured, then the share within
a factor of 2. "Turbulence" is the prototype's σy = σv t fy with CALPUFF's σv (minimum
0.2 m/s); its σv are 1-hour values, so it is also shown scaled to 10-minute samples by
CALPUFF's averaging-time rule, × (10/60)^0.2 = 0.70. AERMOD is its Eq. 77 with
σv² = 3.6u\*² + 0.35w\*² (minimum 0.2 m/s). Briggs is the current model, with the class as
noted.

**Project Prairie Grass** (1956; 10-minute continuous releases at 0.46 m, arcs 50–800 m;
56 runs, 280 arc values). σy from Irwin's analysis (`PGrassOBSAnalysis.txt`) and u\*, w\*,
L, mixing heights and wind from the AERMOD files in the ASTM D6589 archive
(`PGRSURF.MET`), both from https://harmo.org/jsirwin/. Classes for Briggs come from L and
z0 (class-centre 1/L = a + b log10 z0, after Golder 1972, as tabulated in Seinfeld and
Pandis); Prairie Grass classes were not recorded.

| Group | n | Briggs | Turbulence (1 h) | Turbulence (10 min) | AERMOD |
|---|---|---|---|---|---|
| All | 280 | 0.78 / 75% | 1.45 / 74% | 1.02 / 81% | 0.97 / 83% |
| Unstable | 165 | 0.65 / 76% | 1.29 / 89% | 0.90 / 90% | 0.90 / 87% |
| Stable | 115 | 1.01 / 74% | 1.72 / 53% | 1.20 / 70% | 1.08 / 77% |
| 50 m | 56 | 0.60 / 73% | 1.23 / 93% | 0.86 / – | 1.01 / 91% |
| 800 m | 56 | 1.03 / 75% | 1.70 / 57% | 1.19 / 75% | 0.92 / 73% |

**Project Sagebrush Phase 1** (2013; continuous releases at 1.5 m, 10-minute samples, arcs
200–3,200 m; daytime, classes A–D; 169 values). σy (second-moment, non-truncated profiles)
were read from the vector data of Fig. 212 of NOAA Tech. Memo OAR ARL-268 and matched to
each 10-minute bag's u\*, z/L (sonics R3, R4), 10 m wind and σA class from Tables 19–23;
mixing heights are the mean radiosonde values of Table 18; w\* from u\*, L and the mixing
height. The extracted table is `tests/data/tracer/sagebrush1_sigma_y_10min.csv`. Briggs uses the
report's σA class.

| Group | n | Briggs | Turbulence (1 h) | Turbulence (10 min) | AERMOD |
|---|---|---|---|---|---|
| All | 169 | 0.55 / 60% | 1.11 / 99% | 0.77 / 92% | 0.66 / 81% |
| 200 m | 21 | 0.47 / 33% | 1.17 / 100% | 0.82 / 100% | 0.89 / 100% |
| 800 m | 42 | 0.57 / 69% | 1.13 / 100% | 0.79 / 98% | 0.68 / 93% |
| 3,200 m | 22 | 0.50 / 45% | 0.81 / 95% | 0.57 / 77% | 0.39 / 18% |

The current Briggs curves are about 2× too narrow against Sagebrush, as Finn et al. (2016)
found; AERMOD, whose constants come from Prairie Grass, fits Prairie Grass best and falls
short at Sagebrush's longer distances. The prototype (1-hour basis, as used in the maps) is
1.1× Sagebrush and 1.45× Prairie Grass; Sagebrush found averaging time mattered little
(10–60 min), so the 1-hour values are the fairer comparison there.

## Other checks of the prototype

- **Real temperature.** Using Open-Meteo's 2 m temperature instead of an assumed 280 K
  changed no result above by more than 0.2 in any ratio (four HYSPLIT cases).
- **Repository checks** (`validate_explosion.py`, `pytest`) with the prototype switched on:
  the source term, release cases, deposition and envelope checks pass unchanged. Three
  tests fail, as they must for a change of spread: the analytic-puff check (it compares
  with a puff using the Briggs curves; worst deviation 55% against a 15% tolerance) and
  the two golden regression tests (the map numbers change). These would be updated with
  any real change. The real-weather checks (3–4) could not run in this session either way
  (Open-Meteo's archive host is blocked here).

## Wednesday before and after

The site's settings and its saved forecast (pulled Nov. 23, 20:34 UTC), noon blast,
8 hours, four weather models with the deposition spread; only the spread scheme differs.

| Wednesday noon | 100%, current | 100%, prototype | 20%, current | 20%, prototype |
|---|---|---|---|---|
| Ground ≥100 µg/ft² | 24 mi | 5.9 mi (Middletown) | 5.5 mi | 1.8 mi (Middletown) |
| Ground ≥40 µg/ft² | 45 mi | 9.6 mi | 14 mi | 4.0 mi |
| Ground ≥5 µg/ft² | 112 mi | 40 mi | 56 mi | 13 mi |
| Hourly air ≥ PAC-1 | 56 mi | 8.4 mi | 13 mi | 3.3 mi |
| Peak hourly air | 1,031 µg/m³ | 765 µg/m³ | 206 µg/m³ | 153 µg/m³ |

The far zones shrink 3–6×, but the wider cloud near the plant puts Middletown in the
100 µg/ft² zone in both cases (forecast pulled Nov. 23; see TURBULENCE.md for the current one). See `wednesday_before_after.png`. The site was not changed.

## Related check: wind-grid resolution

The model samples winds on a 5×5 grid (about 150 km apart) around the plant. Rerunning
the Wednesday Nov. 25 noon forecast (EPA permit case, 8 hours) with 1×1, 9×9, 15×15 and,
for GFS, 21×21 grids changed distances, areas and peaks very little (RRFS: ground ≥100
µg/ft² at 12 mi on every grid; air ≥ PAC-1 at 18–20 mi), but turned the cloud's path by
4–8° by the end of the run. A finer grid did not converge on one path (GFS 21×21 vs 15×15
still overlapped only about 56% at 5 µg/ft²). The site's ±5° direction spread contained
98–100% of the 15×15 footprint.

## Limits of this test

- Four cases, one site, one release, five hours each.
- HYSPLIT's particle results get noisy far downwind and in thin layers.
- The deposition match uses fixed speeds; the vertical ×2 is not a physical scheme.
- For past dates our model reads Open-Meteo's HRRR at 25 points, HYSPLIT reads NOAA's
  full HRRR grid; part of any difference is the weather input.

## HYSPLIT licence

HYSPLIT's end-user licence (`document/EULA.txt` in the distribution) restricts
redistributing the software, and redistributing results based on NOAA ARL **forecast**
weather without NOAA's permission. These runs used archived weather. HYSPLIT itself and
NOAA's weather files are not in this repository; only our inputs and the numbers above.

## References

- Draxler, R. R., 1976: Determination of atmospheric diffusion parameters. *Atmos.
  Environ.*, **10**, 99–105. (Functions as printed in Scire et al. 2000.)
- Draxler, R. R., and G. D. Hess, 1997: Description of the HYSPLIT_4 modeling system.
  NOAA Tech. Memo. ERL ARL-224 (revised), https://repository.library.noaa.gov/view/noaa/31133.
- EPA, 2026: AERMOD model formulation. EPA-454/B-26-003,
  https://gaftp.epa.gov/aqmg/SCRAM/models/preferred/aermod/aermod_mfd.pdf.
- Finn, D., and Coauthors, 2016: Project Sagebrush: Revisiting the value of the horizontal
  plume spread parameter σy. *J. Appl. Meteor. Climatol.*, **55**, 1305–1322,
  https://repository.library.noaa.gov/view/noaa/52272.
- Finn, D., R. M. Eckman, Z. Gao, and H. Liu: Mechanisms for wind direction changes in the
  very stable boundary layer. Manuscript, https://repository.library.noaa.gov/view/noaa/20853.
- Barad, M. L., Ed., 1958: Project Prairie Grass, a field program in diffusion. Geophys.
  Res. Pap. 59, Air Force Cambridge Research Center; data as distributed by J. S. Irwin,
  https://harmo.org/jsirwin/Tracer_Data.html.
- Finn, D., K. L. Clawson, and Coauthors, 2015: Project Sagebrush Phase 1. NOAA Tech.
  Memo. OAR ARL-268, doi:10.7289/V5VX0DHV, https://repository.library.noaa.gov/view/noaa/11188.
- Irwin, J. S., 1983: Estimating plume dispersion—A comparison of several sigma schemes.
  *J. Climate Appl. Meteor.*, **22**, 92–114. (Abstract only.)
- NOAA ARL, Project Sagebrush Phase 2 (technical memorandum),
  https://repository.library.noaa.gov/view/noaa/15646.
- Paumier, J. O., and R. W. Brode, 1998: Comparison of CALPUFF modeling results to two
  tracer field experiments. EPA-454/R-98-009,
  https://gaftp.epa.gov/aqmg/SCRAM/models/other/calpuff/tracer.pdf.
- Scire, J. S., D. G. Strimaitis, and R. J. Yamartino, 2000: A user's guide for the CALPUFF
  dispersion model (version 5). Earth Tech, https://calpuff.org/calpuff/download/CALPUFF_UsersGuide.pdf.

- Emerson, E. W., and Coauthors, 2020: Revisiting particle dry deposition and its role in
  radiative effect estimates. *Proc. Natl. Acad. Sci. USA*, **117**, 26076–26082,
  doi:10.1073/pnas.2014761117.
- Heffter, J. L., 1965: The variation of horizontal diffusion parameters with time for
  travel periods of one hour or longer. *J. Appl. Meteor.*, **4**, 153–156. (Not checked
  for this test.)
- Stein, A. F., and Coauthors, 2015: NOAA's HYSPLIT atmospheric transport and dispersion
  modeling system. *Bull. Amer. Meteor. Soc.*, **96**, 2059–2077.
- Zhang, L., S. Gong, J. Padro, and L. Barrie, 2001: A size-segregated particle dry
  deposition scheme for an atmospheric aerosol module. *Atmos. Environ.*, **35**, 549–560,
  doi:10.1016/S1352-2310(00)00326-5.
