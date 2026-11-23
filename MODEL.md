# Puff dispersal map

`puff_dispersal.py` takes a release location, a start time and a particle mass. It
fetches the winds for that period, runs a Gaussian puff model, and writes a single
self-contained HTML map with an hour-by-hour slider. The page shows:

- ground-level air concentration, as the hourly mean, as the highest time-step value
  within each hour (the short-term peak), and as a snapshot of the cloud at the end of
  each hour;
- cumulative deposition;
- ALOHA-style threat zones: the area where a running 60-minute average, the short-term
  peak, or the cumulative deposition has reached each of three levels of concern,
  editable in the page;
- with `--ensemble`, a wind-uncertainty view: the highest value of several runs with
  the wind turned a few degrees either way,

with puff positions, wind vectors, the airborne centre's track, and a mass budget
(airborne / dry deposited / wet deposited) for each hour. The page can also download
equivalent NOAA HYSPLIT input files for a cross-check. The command under "Run it" makes an
example map.

## Run it

```bash
pip install numpy          # only dependency (scipy used if present, not required)

python3 puff_dispersal.py --lat 39.74 --lon -104.99 \
    --time 2024-06-01T08:00-06:00 --particle-mass 25ng --hours 24 -o denver.html
```

| Option | Default | Meaning |
|---|---|---|
| `--lat`, `--lon` | required | release point |
| `--time` | now | release start, ISO 8601. Naive = UTC; an offset (`-06:00`) is also used for display |
| `--particle-mass` | `10ng` | mass of **one** particle (`kg g mg ug ng pg t`; bare number = kg), or a size distribution `MASS:FRACTION,…` |
| `--particle-diameter` | – | sizes by diameter instead: `3um` or `1um:0.25,10um:0.75` |
| `--size-preset` | – | a named size mix: `fume`, `mixed` or `soil-bound` (see Particle sizes) |
| `--density` | 1000 | particle density, kg/m³ (1000 gives the aerodynamic diameter) |
| `--material` | – | material preset, currently `lead-azide` (see Materials) |
| `--tracked-fraction`, `--tracked-name` | 1, – | share of the material that is the tracked substance, and its name for labels |
| `--release-mass` | `1kg` | total particulate mass released; concentrations scale linearly with it |
| `--release-duration` | 1 | hours of continuous release (0 = one instantaneous puff) |
| `--release-height` | 10 | m above ground |
| `--hours` | 24 | simulation length (1–240) |
| `--wind 5@270` | – | skip Open-Meteo and use a constant wind (m/s @ direction from) |
| `--grid` | 260 | map cells along the longer side |
| `--extent-km` | fit plume | fix the map to a square of this half-width around the source, for near-field detail |
| `--wind-grid` | 5 | N×N Open-Meteo points for a spatially varying wind field |
| `--weather-model` | `ensemble` | `ensemble`, `best-match`, or Open-Meteo model names separated by commas (see Weather models) |
| `--no-pressure-levels` | off | ignore upper-level winds and extend the 100/120 m wind with a power law |
| `--ensemble`, `--dir-spread` | 1, 10 | number of wind-direction runs and the ± range in degrees (see Wind uncertainty) |
| `--met-cache FILE` | – | store Open-Meteo responses in a JSON file and reuse them on later runs |
| `--land-use` | `grass` | surface type for dry deposition: `grass`, `crops`, `forest`, `urban`, `desert`, `water` |
| `--vd-extra` | – | use settling plus this fixed speed (m/s) instead of the size-resolved scheme |
| `--rain` | from weather | override precipitation everywhere (mm/h) to test wet removal; one scavenging coefficient applies to every particle size, so removal of 1–3 µm particles is overstated |

### Explosion source

`--explosive-mass` switches the source to an instantaneous explosion cloud:

| Option | Default | Meaning |
|---|---|---|
| `--explosive-mass` | – | mass of material that detonates, e.g. `5t` |
| `--specific-energy` | 4.184 | MJ released per kg of material (TNT = 4.184; a material preset sets its own) |
| `--shots` | 1 | number of equal charges fired together; the material is the total, the cloud height comes from one charge |
| `--confinement` | `open` | `earth-covered` halves the cloud height unless `--church-factor` is given |
| `--airborne-fraction` | 1.0 | fraction of the tracked substance lofted as particulate; 1.0 is the bounding case |
| `--cloud-layers` | 5 | number of puff layers spread from the ground to the cloud top |
| `--cloud-radius-frac` | 0.25 | initial horizontal σ as a fraction of cloud-top height |
| `--church-factor` | 1.0, or 0.5 when earth-covered | multiplier on the cloud-top height |

How the source is built:

- Energy is the material mass times its specific energy, then converted to a TNT
  equivalent at 4.184 MJ/kg.
- The cloud-top height comes from the Church formula used by LLNL HotSpot,
  H = 76·W^0.25 (H in metres, W in pounds of TNT).
- The lofted mass is split evenly over the layers and across the particle-size bins.

```bash
python3 puff_dispersal.py --lat 39.74 --lon -104.99 --time 2024-06-01T08:00-06:00 \
    --explosive-mass 5t --specific-energy 1.64 \
    --particle-mass "1pg:0.25,30pg:0.25,1ng:0.25,30ng:0.25" --density 1720 --hours 24
```

### Materials

`--material lead-azide` tracks the lead in the material, not the material itself. It sets:

- the tracked share: 71.1% of lead azide, Pb(N₃)₂, is lead by mass;
- specific energy 1.54 MJ/kg and particle density 9,500 kg/m³ (lead oxide);
- the `mixed` size preset;
- units: air in µg/m³, deposition in µg/ft²;
- air levels: 0.15 µg/m³ (the US lead standard, a 3-month average), 1.5 µg/m³, and
  32 µg/m³ (DOE PAC-1 for lead; check the current revision);
- deposition levels: 5, 40 and 100 µg/ft², EPA's 2024 dust-lead action levels for
  floors, window sills and window troughs. These are indoor clearance levels, used
  here only as a screening reference for outdoor fallout.

Any option given explicitly overrides the preset.

### Particle sizes

Nothing about the particle sizes from a particular event is measured in advance, so
the size mix is an assumption. Run more than one and compare:

| `--size-preset` | Diameters (equal or stated shares) | Meant for |
|---|---|---|
| `fume` | 0.3 µm 30%, 1 µm 40%, 3 µm 20%, 10 µm 10% | condensed metal fume; stays airborne longest |
| `mixed` | 1, 3, 10, 30 µm, 25% each | a middle case |
| `soil-bound` | 10, 30, 100 µm, a third each, at 2,650 kg/m³ | material carried on entrained soil dust; falls out soonest |

### How much is respirable

No measured lead emission factor was found for this kind of detonation, so the script
offers documented reference cases instead of a single "most probable" value:

| `--release-case` | Respirable share of the tracked substance | Basis |
|---|---|---|
| `upper-bound` | all of it, in the chosen size mix | bounding; no data behind it |
| `tnt-equivalent` | respirable mass equal to the charge's TNT-equivalent mass | the bounding rule in DOE-HDBK-3010 for detonations in or next to solid metal |
| `20-percent` | 20% | the general upper-bound precedent quoted in DOE-HDBK-3010 |

In the last two cases the respirable share uses the `fume` sizes and the rest is put
into coarse 30 and 100 µm particles at 2,650 kg/m³, carried on soil and debris. The
coarse sizes are an assumption. It is consistent with Aurell et al. (2015), who found
large amounts of soil entrained in detonation plumes and higher particle emissions
from soil-covered detonations than from surface ones. `--respirable-fraction` sets
the share directly. Both handbook rules were written for other materials, so treat
them as reference points, not predictions.

### Confined and multiple charges

The Church cloud-height formula is for an open-air charge on the surface.
`--confinement earth-covered` halves that height for a charge inside an earth-covered
or bermed structure. The factor of one half is a screening assumption, not a validated
value; set `--church-factor` to test others. A lower cloud gives higher concentrations
near the site. How much material is lofted is set separately with `--airborne-fraction`.

### Weather models

By default the script runs a built-in ensemble of forecast models: ECMWF, GFS, ICON,
GEM, UKMO and Météo-France, plus HRRR when it covers the whole run. A model that
fails or does not reach the end of the run is skipped with a note.

- The map shows the first model in the list (ECMWF by default).
- The page's "weather-model spread" toggle shows the highest value any model gives,
  with each model allowed ±5° of direction error, and draws the other models' paths.
- `--weather-model gfs_seamless` runs one model. A comma-separated list runs those
  models, showing the first. `best-match` uses Open-Meteo's single default forecast.
- Historical dates and `--wind` always use a single source.

Each model needs its own weather download, so a default run makes about seven times
the requests of a single-model run. Use `--met-cache` to avoid repeating them. Some
models supply fewer levels or fields in this feed; ECMWF, for example, has three
wind levels aloft and no mixing height, so a default by stability class is used.

### Wind uncertainty

`--ensemble 5 --dir-spread 10` runs the model five times with the whole wind field
turned by −8°, −4°, 0°, +4° and +8°. Each run is then smeared by ±2° so that together
they cover ±10° without gaps. The page shows the central run; its "wind uncertainty"
toggle shows the highest value any direction gives, and draws the other paths. That
view is the area that could be affected, not the area that will be affected at once.
With several weather models, each model is turned through the same offsets.

### Water spray at the source

`--spray-flow L/MIN` adds a wetted zone around the source. It is a square with the
same area as a circle of radius `--spray-radius` (default 50 m), reaching from the
ground to `--spray-height` (default 30 m), between `--spray-start` and
`--spray-start + --spray-duration` minutes. Each puff is sub-stepped through the zone.

For each particle size the capture rate is Λ = 3·J·E / (2·D), where:

- J is the water flux;
- D is the drop diameter (`--spray-drop`, default 1 mm);
- E is Slinn's collection efficiency (Brownian diffusion, interception and inertial
  impaction), which is very small for 0.1–2 µm particles.

The captured mass is deposited in the zone, counted as wet deposition, and also
reported as "captured by spray".

This models spray acting on a cloud in open air. It does not represent wet earth or
sand covering a charge, which acts on the material before it is airborne; use
`--airborne-fraction` for that.

### Threat zones and HYSPLIT export

| Option | Default | Meaning |
|---|---|---|
| `--loc` | `0.15mg,5mg,15mg` | yellow, orange and red levels of concern (per m³, or with a volume such as `0.2ug/cm3`) |
| `--loc-labels` | generic dust references | `\|`-separated names shown beside each level |
| `--dep-loc` | `1mg,10mg,100mg` per m² | three deposition levels for the threat-zone view, e.g. `5ug/ft2,40ug/ft2,100ug/ft2` |
| `--dep-loc-labels` | – | `\|`-separated names for the deposition levels |
| `--scale-max` | run maximum | fix the top of the air-concentration colour scale, e.g. `0.2ug/cm3` |
| `--scale-min` | – | show only air concentrations at or above this value, e.g. `0.2ug/cm3`; the colour scale starts here and spans `--decades` above it, and the page says so when nothing qualifies |
| `--units` | `mass` | units the page opens in: `mass` (per m³, automatic prefix), `ugm3` (µg/m³), `ugft2` (air in µg/m³, deposition in µg/ft²), `cm3` (µg/cm³) or `count` |
| `--decades` | 5 | initial colour-scale range in decades (adjustable in the page) |
| `--hysplit DIR` | – | also write `CONTROL`, `SETUP.CFG` and `README.txt` for HYSPLIT into DIR |

The default levels are generic dust references:

- yellow: the US PM10 24-hour standard;
- orange: OSHA's respirable-dust limit for particulates not otherwise regulated;
- red: OSHA's total-dust limit for the same.

They have different averaging times, so for a real material replace them with its
DOE PAC or AEGL values.

`--help` lists the remaining tuning options: time step, puff cap, extra dry-deposition
velocity, and the wet-scavenging coefficient.

## Worked scenario

`scenarios/iowa-aap-lead-azide/` holds a complete worked case: the map,
saved weather forecasts, and a README on how to rerun all of it.

## Choosing a model for an explosive dispersal event

| Model | Fit for a detonation | Role here |
|---|---|---|
| **AERMOD** (EPA preferred, near field) | Poor | Not used. It assumes steady-state hourly plumes from continuous sources (stacks, roads), within about 50 km. It has no puff memory, so a burst lasting a few minutes breaks its assumptions. It also needs AERMET-processed surface and upper-air data. It is the right tool only for a permitting question about routine emissions. |
| **CALPUFF** (EPA alternative since 2017) | Technically capable | Not integrated. It is a puff model, so it handles a single burst. Its strengths are CALMET's terrain-adjusted 3D winds, puff splitting and resistance-based deposition. The cost is a heavy set-up and case-by-case regulatory approval. This script is a lightweight model of the same family (Gaussian puffs, PG/Briggs σ curves, CALPUFF-style wet scavenging), without terrain or CALMET. |
| **ALOHA** (EPA/NOAA, emergencies) | Partial | Its threat-zone presentation is reproduced in the page. ALOHA itself is a Windows GUI that models gases and vapours, not particulates, and has no API to drive. It suits the gaseous products (e.g. NOx) and flammable-vapour overpressure, not the dust cloud. |
| **HYSPLIT** (NOAA) | Good, especially beyond about 10–50 km | Exported. It uses 3D gridded meteorology, supports vertical line sources and particle settling, and is used for volcanic-ash and radiological plumes. `--hysplit` (or the page buttons) writes an equivalent run: the same vertical line source, one pollutant per particle size, GDAS1 met file names. |
| **HotSpot** (LLNL) | Designed for explosive releases | It is the source of the Church cloud-rise formula used here. It is a good independent near-field cross-check. |

Suggested combination:

1. **First hour, within about 10 km:** use this script with `--extent-km`. It gives
   the explosive source term, the short-term peaks, and threat zones against the
   material's own PAC/AEGL values.
2. **Hours to days, tens to hundreds of km:** run HYSPLIT from the exported CONTROL
   file with the finest ARL meteorology available (HRRR or NAM in the US, otherwise
   GFS 0.25°).
3. **Gaseous products and blast:** use ALOHA for these; this model does not cover them.

## Weather

Hourly 10 m wind, cloud cover, shortwave radiation, precipitation and boundary-layer
height come from [Open-Meteo](https://open-meteo.com), with no API key:

- dates more than about 6 days in the past: ERA5 reanalysis (archive API, back to 1940);
- recent dates and up to about 16 days ahead: the forecast API.

If one fails, the script tries the other.

The data is fetched on a 5×5 grid around the source, sized to how far the wind could
carry the puffs. It is interpolated bilinearly in space and linearly in time.

The forecast API also supplies wind and height on pressure levels (for example 950 to
700 hPa), which the model uses for winds aloft. The archive API returns none, so
historical runs fall back to a power-law profile above 100 m.

## Model

- **Winds aloft**: Open-Meteo's 100 m (ERA5) or 120 m (forecast) wind is used with the
  10 m wind, blended between them on a log-height scale. Above that, the wind is
  interpolated linearly through the pressure-level winds where the source has them.
  Otherwise it follows the stability power law up to the mixing height.
- **Particle**: the equivalent-sphere diameter comes from mass and density. Settling
  velocity uses Stokes' law with the Cunningham slip correction, switching to
  Schiller–Naumann drag above Re ≈ 0.1.
- **Puffs**: released every time step during the release period. Each puff is
  advected by the interpolated wind, scaled to its transport height with a
  stability-dependent power law.
- **Stability**: Pasquill–Gifford class (A–F) from wind speed, solar radiation and cloud
  cover (Turner method).
- **Growth**: Briggs rural σy and σz curves, using the virtual-distance method so a puff
  keeps growing correctly when stability changes from hour to hour.
- **Vertical**: tilted puff (the centre sinks at the settling velocity), with image
  reflections at the ground and at the mixing height, becoming well mixed once
  σz > 1.6 × mixing height.
- **Residual layer**: when the mixing height falls (usually around sunset), the share of
  each puff above the new top is moved to a residual layer (Stull 1988, ch. 1). It moves
  with the puff but neither deposits nor adds to ground-level air. When the mixing height
  grows back into it, the overlapping share mixes down again; rain still washes it out.
  For a well-mixed puff the share above the new top is 1 − h_new/h_old; for a puff still
  Gaussian under the lid it comes from the reflected Gaussian. Without this (the old
  behavior, `--no-residual-layer`), a falling lid folds the whole puff into the shallow
  night layer and overstates ground-level air and deposition downwind after sunset.
  Simplification: the residual mass moves with the puff's own transport wind, not the
  wind at its height.
- **Deposition**: the dry flux is v_d·C at ground level. v_d comes from the
  size-resolved scheme of Zhang et al. (2001): settling plus transfer through the air
  and onto the surface by Brownian diffusion, impaction and interception. It depends
  on particle size and density, the 10 m wind and the surface type (`--land-use`,
  default `grass`). The aerodynamic part assumes neutral stability, and the land-use
  constants are as recalled from the paper and should be checked against it.
  `--vd-extra` switches back to settling plus a fixed speed. Wet
  scavenging is Λ = 10⁻⁴ s⁻¹ per mm/h of rain. Both deplete the puff's mass, so mass
  is conserved: airborne + deposited = released.
- **Output**: puffs are integrated onto the grid exactly (cell-averaged Gaussians),
  then log-quantised, zlib-compressed and embedded. The page decodes them in the
  browser.

**Explosion validation.** `validate_explosion.py` runs the checks for 5 t at
1.4–1.64 MJ/kg; its output is in `validation_output.txt`. It covers:

- the source term, checked against HotSpot's published examples;
- that the 60-minute threat-zone metric always lies between the hourly mean and the
  peak, and that the HYSPLIT CONTROL file is structurally consistent;
- the 5-layer cloud against an analytic Gaussian puff (within 11% at 5 km, within 3%
  beyond 20 km);
- mass conservation in real-weather runs (day and night);
- sensitivity to the energy range;
- the dry-deposition curve (lowest near 1 µm, never below settling, rising with wind)
  and the respirable shares of the release cases;
- the material preset, multi-charge cloud height, interpolation through upper-level
  winds, the plume turning with the wind, and the uncertainty view containing the
  central run with no gaps (no network needed);
- the map's colour range;
- near-field resolution.

**Continuous-release checks.** Gridded deposition sums to the model's deposited mass. For a
continuous ground-level release in steady, neutral wind, the hourly concentration is
within about 6–13% of the analytic Gaussian plume at 5–10 km. It reads lower close to
the source because each grid cell is averaged.

## Limitations

This is a screening tool, not a regulatory or emergency-response model:

- winds come from a forecast or reanalysis on a coarse 5×5 grid; historical runs have
  no measured winds aloft;
- the particle sizes, the lofted fraction and the confined-charge cloud height are
  assumptions, and the results are sensitive to all three;
- there are no terrain effects, buildings, plume rise, or resuspension;
- Pasquill–Gifford σ values are empirical fits from flat terrain;
- puffs grow along the Briggs curves, which describe a continuous plume averaged over
  about an hour. A single instantaneous puff spreads more slowly at first, so near the
  source the real cloud may be narrower, with higher peaks over a smaller area, than the
  model shows. The difference shrinks downwind and over an hour;
- settling is counted twice: the puff centre sinks at the settling velocity, and the
  deposition velocity at the ground also includes it. This can remove somewhat too much
  of the largest particles (10 µm, about 3 cm/s) near the source; for breathable sizes
  the effect is negligible;
- near-source peaks are smoothed by the grid cell size (printed when the script runs
  and shown in the page footer); use `--extent-km` for near-field numbers;
- the explosion cloud uses an empirical rise formula. Observed clouds (e.g. Beirut 2020)
  have risen less than such formulas predict, and a lower cloud means higher
  near-field ground concentrations;
- an instantaneous release uses few puffs, so far downwind (especially in stable,
  sheared night-time flow) the layers can separate into distinct blobs;
- blast, fireball and gaseous combustion products (e.g. NOx) are not modelled. A gas
  can be approximated with a tiny particle mass, which gives zero settling.

## Viewing the HTML

Everything the page needs (code, data, styles) is inside the file, and it opens
straight from disk. The only thing it fetches is basemap tiles: Esri gray canvas,
topographic or satellite, selectable in the page. With no network, or
with "none" selected, the plume still renders on a plain background.
