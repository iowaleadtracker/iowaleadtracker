# EPA public air data, Nov. 25, 2026

Downloaded Nov. 25, 2026, 17:43 UTC (11:43 a.m. CST) from the public layers behind EPA's
"Iowa Army Ammunition Plant Response Data Viewer"
(https://experience.arcgis.com/experience/1ddcf8b9d8314971b00dac8893ae9cd6), which EPA's
Nov. 25 news release links as its 5-minute air monitoring data
(https://www.epa.gov/newsreleases/epa-collects-over-1200-air-land-and-water-samples-ahead-iowa-army-ammunition-plant).

- `epa_xact_public_viewer_20261125_1743Z.csv`: every record in the layer
  `IAAAP_Xact_Data_Public_Viewer` (215 records, four stations, 13:00 to 17:41 UTC). The
  layer's fields are a time, a concentration in µg/m3 and a station; it does not name the
  substance measured or give a detection limit. EPA's release describes the data as its
  air monitoring for lead.
- `epa_air_stations_20261125.csv`: the 43 sites in the layer
  `Air_Sampling_and_Monitoring_Location`, with the instruments EPA lists at each. No results
  for these instruments were in the public layers when this was downloaded.

Distances and bearings are from the plant (40.825518, -91.266502), computed here. These are
EPA's preliminary real-time data as posted, not validated results. This is a snapshot; EPA's
layer keeps changing.
