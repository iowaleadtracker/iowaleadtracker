# Data for the monitor-placement brief

- `model_fields.npz`: the three modeled fields the map is drawn from, each the highest
  hourly mean lead in air at the ground (kg/m³) for the lowest published case (7% of the
  lead airborne as fine dust), cut to the map's area plus a margin. Arrays `forecast_*`,
  `analysis_*` and `hysplit_*`, each with `lon`, `lat` and `air` (rows are latitudes).
  Saved by `../../scripts/aerial_map.py` from the model runs that
  `../../scripts/reproduce.sh` makes.
- `epa/epa_air_stations.csv`, `epa/epa_xact_public_viewer.csv`: EPA's public site list and
  real-time readings, downloaded Nov. 26, 2026, 12:37 UTC (6:37 a.m. CST) with
  `../../scripts/epa_fetch.py`. These are EPA's preliminary values as posted. The
  `miles_from_plant` and `bearing_from_plant` columns are from the plant point the site
  used, not from the magazines; the brief computes its own.

The Army's map images, where they sit on the ground (`army_georef.json`) and the modeled
source (`source.json`) are in [`../../data/`](../../data/).
