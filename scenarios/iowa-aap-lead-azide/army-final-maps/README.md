# The Army's final maps, as outlines for the site's maps

The zones on the U.S. Army's final "Mitigated 0.26" maps for the Nov. 25, 2026 blast
(stamped a/o 250700NOV26), traced and placed on the ground so the site's maps can draw
them. On the maps for the 9 a.m. blast, the "Army's final maps" box under the map draws
them over either model's result.

They are the Army's forecast, made before the blast, for 26% of the lead becoming
airborne. They are not measurements, and the tracing and placing are this project's, not
the Army's. The site's warnings apply: don't use this to decide if you're safe; follow
official instructions. The Army's own maps are at
https://www.army.mil/asc#org-iowa-army-ammunition-plant.

## What is here

| File | What |
|---|---|
| `army_mitigated026_air_a-o_250700NOV26.jpg` | the Army's final air map. The ground map is in [`../postmortem/monitor-placement-brief/data/army/`](../postmortem/monitor-placement-brief/data/README.md) |
| `georef.json` | where the air map sits on the ground. The ground map's placement is the brief's `data/army_georef.json` |
| `outlines.json` | the traced zones as lines of latitude and longitude, with the name and note the map page shows |
| `make_outlines.py` | makes `outlines.json`, and `georef.json` with `--place` |

## What is drawn

- **On the air views:** the edge of the path the Army shaded for lead in air of
  0.18 µg/m³ or more (the detection limit of its lead air sampling method, by the map's
  legend), and the lines the Army labeled T+0.5, T+2, T+3, and T+5 hours where they cross
  that path.
- **On the deposition view:** the edges of the Army's zones for lead on the ground of
  5 µg/ft² or more (dashed) and 100 µg/ft² or more (solid).

## How it was made

1. **Placing.** Each map is a small picture, about 0.6 mile per pixel, over a base map
   with county lines. `place_army_map.py` in the brief's folder fits a Mercator scale and
   an offset so that public county boundaries fall on the picture's county lines. The fit
   is good to about a pixel.
2. **Tracing.** Each zone is picked out by its color. Gaps left by the county names
   printed over it are closed, and the edge is taken where the smoothed zone is half
   covered.
3. **Hidden part.** The Army's magenta plant marker covers the first miles of every zone.
   The edges stop where the marker begins; nothing is drawn under it.

```bash
pip install numpy scipy matplotlib pillow
python3 make_outlines.py            # trace, using the saved placement
python3 make_outlines.py --place    # place the air map again first (needs the network)
```

The site build reads `outlines.json` (`--reference-outlines` in `puff_dispersal.py`). It
does not trace anything.

## Limits

- The pictures are coarse. A line here can be off by about 0.6 mile from placing alone,
  and the edges of the shading are soft.
- The Army's maps are for one case, 26% of the lead airborne, on the Army's own forecast
  weather. They stay the same whichever case the site's map shows.
- The Army's maps don't say how their zones were computed. The air zone looks like the
  cloud's whole path over the hours, not one hour.
- Where the source is under the Army's marker can't be read from the maps.
