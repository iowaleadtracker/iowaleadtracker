# HYSPLIT on archived weather, for the map's HYSPLIT view

NOAA's HYSPLIT model (Stein et al. 2015) run for the Nov. 25, 2026 blast on archived
weather, saved so the site's archived-weather maps can show it. On those maps, the "NOAA
HYSPLIT" button under the map switches from the site's model to this run. It is drawn in
the four colors of HYSPLIT's own plots (cyan, green, blue, and yellow, lowest to highest),
between the same lowest and highest levels as the site's map, so switching back and forth
compares the two.

It is a second model's estimate for the same assumed release. It is not a measurement and
not a forecast from NOAA: this project ran HYSPLIT itself. The site's warnings apply to it: don't use it to decide if you're safe; follow official
instructions.

## What is here

| File | What |
|---|---|
| `CONTROL`, `SETUP.CFG` | the inputs HYSPLIT was run with |
| `overlay_0900.npz` | the run's output as the maps read it: hourly mean lead in the lowest 10 m of air and lead on the ground since the release, for 8 hours, on a 0.006° grid |
| `make_overlay.py` | turns the run's output into that file |

## The run

- **Model.** HYSPLIT 5.4.2, public build, `hycs_std`, 200,000 particles.
- **Weather.** NOAA Air Resources Laboratory's archive of the HRRR weather model, files
  `20261125_12-17_hrrr` and `20261125_18-23_hrrr`. This is NOAA's own archive, a different
  copy of HRRR from the Open-Meteo one the site's archived-weather maps use.
- **Release.** 9:00 a.m. CST (15:00 UTC), over 6 minutes, 3,130 kg of lead (all of it; the
  maps scale the result to their case) in the site's four particle sizes (0.3, 1, 3, and
  10 µm at 9.5 g/cm³, 30/40/20/10% by mass), with the site's deposition speeds for those
  sizes (Zhang et al. 2001).
- **Where.** Two vertical lines from 10 m to 251 m, one at each of the two magazines
  (40.8106, −91.2686 and 40.8085, −91.2698), half of the lead from each. The site's
  archived-weather maps start their cloud midway between the two, about 130 m from each.
  The location comes from a reader's tip checked against published imagery; no official
  source confirms it.
- **Output.** Hourly means for 8 hours on a 0.003° grid, at the ground (deposition) and
  in the 0-10 m layer.

HYSPLIT gives every line source the full emission rate, so `make_overlay.py` divides by
the number of lines. It then averages the output 2 x 2 to 0.006°, about the size of the
maps' own cells, and keeps only the area the cloud reaches.

## Making it again

```bash
# in a folder with the two weather files, CONTROL, SETUP.CFG and HYSPLIT's bdyfiles
$HYSPLIT_DIR/exec/hycs_std
$HYSPLIT_DIR/exec/con2asc -icdump -d -x          # one text file per hour
python3 make_overlay.py . overlay_0900.npz
```

The site build does not run HYSPLIT. It reads `overlay_0900.npz` (`--hysplit-overlay` in
`puff_dispersal.py`), scales it to the map's case, and puts it on the map's grid.

## Limits

- HYSPLIT follows particles, so its edges are grainy at low levels. The far end of the
  cloud, and the lowest deposition band, show that grain.
- The run saved hourly means and deposition. The map's "Peak", "Snapshot", and "Levels of
  concern" views are off while HYSPLIT shows, and so are the site's own puffs, path, and
  wind arrows.
- The four colors each cover a quarter of the map's range. With the map's usual range of
  four powers of ten, each color is one power of ten, as on HYSPLIT's own plots. The
  colors are not easy to tell apart for some readers; the legend and the readout under the
  pointer give the numbers.
- HYSPLIT and the site's model were given the same release but not the same copy of the
  weather, and they treat mixing differently. They are two estimates, and neither is a
  check against what happened.
- The amount of lead that got into the air is not known. Both models scale with it.
