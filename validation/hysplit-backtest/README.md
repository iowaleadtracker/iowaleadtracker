# HYSPLIT back-test, November 2026

A comparison of this model against NOAA's HYSPLIT for the same release on four past
afternoons and evenings, using archived weather. It was run on Nov. 24, 2026, to check
how far the published maps could be off and in which direction. **Nothing here changes
the site or the model.** The model variants below were tried in a scratch copy only.

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
- **Widening the cloud everywhere overcorrects in stable air.** A Heffter-style crosswind
  growth plus doubled vertical growth brought the daytime cases to 1.0–2.0× HYSPLIT but
  cut stable-evening peak air to a tenth of HYSPLIT's. Applying it only in classes A–D
  keeps every daytime result at or above HYSPLIT and leaves stable air as it is now.
- **The deposition scheme moves the ground zones a lot but not the air.** Emerson et al.
  (2020) instead of Zhang et al. (2001) changed the ground zones by up to about 50% and
  deposited about a third more lead, but did not change the ratios to HYSPLIT. HYSPLIT's
  own particle deposition scheme deposited about 4.5× more lead than HYSPLIT with our
  deposition speeds (Monday only).

Not yet done: a proper daytime mixing scheme in place of the doubled vertical growth, a
look at why stable-air peaks run low, more days (including the blast day once its HRRR
weather is archived), and the repository's validation checks with any change in place.

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
