# The Army's final maps, as outlines for the site's maps

The zones on the U.S. Army's final "Mitigated 0.26" maps for the Nov. 25, 2026 blast
(stamped a/o 250700NOV26), traced and placed on the ground so the site's maps can draw
them. On the maps for the 9 a.m. blast, the "Army's final forecast" box under the map shades
them green over either model's result, as on the map in the monitor-placement brief.

They are the Army's forecast, made before the blast, for 26% of the lead becoming
airborne. They are not measurements, and the tracing and placing are this project's, not
the Army's. The site's warnings apply: don't use this to decide if you're safe; follow
official instructions. The Army's own maps and updates are at
https://www.army.mil/asc#org-iowa-army-ammunition-plant.

The Army posted the two maps on DVIDS on Nov. 25, 2026 (photo by Lori McFate, Iowa Army
Ammunition Plant; marked public domain there):

- Air map, "Mitigated 0.26 Dispersion": [Deposition Map 2 at 8:00 AM (CST)](https://www.dvidshub.net/image/10118629/deposition-map-2-800-am-cst)
- Ground map, "Mitigated 0.26 Deposition": [Deposition Map 1 as of 8:00 AM (CST)](https://www.dvidshub.net/image/10118630/deposition-map-1-800-am-cst)

The copies traced here were compared with DVIDS's on Nov. 26. Scaled to the same size,
they differ only by compression noise (about 1% of full brightness on average; one pixel
in ten thousand differs noticeably), and DVIDS's carry the same stamp, a/o 250700NOV26.
The "8:00 AM" in DVIDS's titles is not a different version.

## What is here

| File | What |
|---|---|
| `army_mitigated026_air_a-o_250700NOV26.jpg` | the Army's final air map. The ground map is in [`../postmortem/monitor-placement-brief/data/army/`](../postmortem/monitor-placement-brief/data/README.md) |
| `georef.json` | where the air map sits on the ground. The ground map's placement is the brief's `data/army_georef.json` |
| `outlines.json` | the traced zones as lines of latitude and longitude, with the name and note the map page shows |
| `make_outlines.py` | makes `outlines.json`, and `georef.json` with `--place` |

## What is drawn

- **On the air views:** the path the Army shaded for lead in air of
  0.18 µg/m³ or more (the detection limit of its lead air sampling method, by the map's
  legend), and the lines the Army labeled T+0.5, T+2, T+3, and T+5 hours where they cross
  that path.
- **On the deposition view:** the Army's zones for lead on the ground of 5 µg/ft² or more
  and, shaded darker inside it, 100 µg/ft² or more.

## How it was made

1. **Placing.** Each map is a small picture, about 0.6 mile (1 km) per pixel, over a base map
   with county lines. `place_army_map.py` in the brief's folder fits a Mercator scale and
   an offset so that public county boundaries fall on the picture's county lines. The fit
   is good to about a pixel.
2. **Tracing.** Each zone is picked out by its color. Gaps left by the county names
   printed over it are closed, and the edge is taken where the smoothed zone is half
   covered.
3. **Hidden part.** The Army's magenta plant marker is about 14 miles wide on the picture
   and covers about the first 8 miles of every zone, measured from the modeled source.
   The edges stop where the marker begins. The shading closes straight across that gap.

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
