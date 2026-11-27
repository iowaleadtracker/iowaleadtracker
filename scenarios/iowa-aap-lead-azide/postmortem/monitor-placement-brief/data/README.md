# Data for the monitor-placement brief

- `model_fields.npz`: the three modeled fields the map is drawn from, each the highest
  hourly mean lead in air at the ground (kg/m³) for the lowest published case (7% of the
  lead airborne as fine dust), cut to the map's area plus a margin. Arrays `forecast_*`,
  `analysis_*` and `hysplit_*`, each with `lon`, `lat` and `air` (rows are latitudes).
  They were saved from the model runs of the full analysis (see the brief, "How it was
  made"); the code in this folder starts from them and does not rerun the models.
- `ground_fields.npz`: modeled lead on the ground eight hours after the blast (kg/m²)
  for the same 7% case, from two models, cut to where either has 0.1 µg/ft² or more.
  Arrays `tracker_*` and `hysplit_*`, each with `lon`, `lat` and `dep` (rows are
  latitudes). `tracker` is the site's archived-weather map for the Low case, a later
  tracker run than the `analysis` field above: one source midway between the magazines,
  on NOAA's HRRR as Open-Meteo served it at 6:51 p.m. CST on Nov. 25. `hysplit` is the
  same HYSPLIT run as the `hysplit` field above, averaged to a 0.006° grid. Written by
  `../ground_fields.py` from the built map and from the saved HYSPLIT run
  (`overlay_0900.npz` in the scenario's `hysplit-archived/` folder, on the
  `claude/hysplit-overlay` branch until it is merged).
- `source.json`: where the release is modeled from: the two magazines, as latitude and
  longitude and as offsets from the point the site used for the whole plant.
- `epa/epa_air_stations.csv`, `epa/epa_xact_public_viewer.csv`: EPA's public site list and
  real-time readings, downloaded Nov. 26, 2026, 12:37 UTC (6:37 a.m. CST) with
  `../epa_fetch.py`. These are EPA's preliminary values as posted. The `miles_from_plant`
  and `bearing_from_plant` columns are from the plant point the site used, not from the
  magazines; the brief computes its own.
- `army/army_mitigated026_ground_a-o_250700NOV26.jpg`: the Army's final "Mitigated 0.26"
  ground map, issued Nov. 25, 2026, stamped a/o 250700NOV26.
- `army_georef.json`: where that picture sits on the ground, written by
  `../place_army_map.py`.
