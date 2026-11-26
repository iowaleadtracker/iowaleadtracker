# HYSPLIT on the blast day (Wed Nov 25, 2026, 9 a.m. CST)

Inputs for running NOAA's HYSPLIT on the blast with NOAA ARL's archived HRRR, the same
way as the [back-test](../README.md). **Nothing here changes the site or the model.**
HYSPLIT is a reference model, not the truth; its results are not official NOAA or
government material.

## When the weather is available

9 a.m. CST is 15 UTC. NOAA ARL archives HRRR in 6-hour files; every file in November
2026 was posted 0.6–1.0 h after its last hour (checked on the S3 copy,
`noaa-oar-arl-hysplit-pds`, Nov. 25):

| File | Hours (CST) | Expected (CST) | Allows |
|---|---|---|---|
| `20261125_12-17_hrrr` | 6–11 a.m. | about 12:40 p.m. Wed (latest seen: 1:00) | a 2-hour run, 9–11 a.m. |
| `20261125_18-23_hrrr` | noon–5 p.m. | about 6:40 p.m. Wed (latest seen: 7:00); posted 6:43 p.m. | the 5-hour back-test length and the site's 8 hours |

Each file is 3.4 GB; from S3 one took about 2½ minutes here.

## Faster: raw HRRR analyses

NOAA's raw HRRR on AWS (`noaa-hrrr-bdp-pds`) posts each hour's analysis 51 to 54 minutes
after the hour (Nov. 25: 15Z at 15:54, 16Z at 16:53, 17Z at 17:53 UTC). `nowcast_hrrr.sh
15 17` waits for the analyses (`wrfprsf00`, pressure levels), converts each with HYSPLIT's
`api2arl_v4` (about 20 s and 550 MB per hour, full 3 km grid, 1013–50 hPa) and appends it
to `work/hrrr_nowcast_20261125.arl`. Give later hours (e.g. `18 23`) to extend it.
`./run_blast_day.sh nowcast` then runs the `*-analyses` input, which reads that file
with nothing held fixed; its run length (line 5 of the CONTROL, now 8 hours) must end at
or before the last analysis in the file.

This is not the same weather input as ARL's archive: pressure levels every 25 hPa instead
of HRRR's native levels, and analyses without surface fluxes (HYSPLIT then estimates
stability from the temperature and wind profile). It matters: for 9 to 11 a.m. HYSPLIT's
path on these analyses was 7° west of its path on ARL's archive, and its near-field zones
about half the size. `api2arl_v4` needs ecCodes (`apt-get install libeccodes0`). The results are in the
[first comparison](../../../scenarios/iowa-aap-lead-azide/postmortem/README.md).

## Runs

| CONTROL | Hours | Deposition speeds |
|---|---|---|
| `2026-11-25-9am-zhang-early2h`, `-emerson-early2h` | 2 | Zhang, Emerson; on the first archive file (the comparison's reference runs until the second file was posted) |
| `2026-11-25-9am-coarse-early2h` | 2 | 10, 30 and 100 µm at soil density (2.65 g/cm³), each carrying all of the lead, with the tracker's Zhang speeds for those sizes; on the first archive file |
| `2026-11-25-9am-zhang-lofted` | 4 | Zhang; on both archive files, with the cloud released from 250.9 to 501.8 m instead of 10 to 250.9 m (a test of a cloud that rose above the modeled top) |
| `2026-11-25-9am-zhang-analyses` | 8 | Zhang; on the hourly pressure-level analyses, 0.005° grid shifted southwest |
| `2026-11-25-9am-zhang` | 8 | Zhang; on both archive files (the comparison's reference run) |
| `2026-11-25-9am-emerson` | 8 | Emerson; on both archive files |

Made from the back-test's Monday (overcast) inputs. Changed: start `26 11 25 15 00`,
the two met files, and the grid. The 2-hour inputs keep a grid centred on the plant
spanning 3° × 4° (about 330 × 340 km), chosen before the wind direction was known. The
8-hour inputs use a 3.6° × 4.5° grid centred 0.9° south and 1.1° west of the plant,
because the cloud travels about 125 miles southwest in 8 hours and would have reached
the southern edge of the first grid. The cell edges of the two grids line up, and the
8-hour runs reproduce the 2-hour runs' results. Release, particle sizes, output levels
(0, 0–10 m, 0–100 m) and `SETUP.CFG` (200,000 particles) are as in the back-test.
The three Zhang inputs also write a second grid, `csnap`: a snapshot of the 0–10 m layer
every 30 minutes, for comparing the cloud's position with the time marks on the Army's
map. Adding it does not change the hourly output (`cdump` is byte-identical).

These inputs start at the scenario's nominal point. The first comparison's monitor section
models the release from two magazines about 1.8 km south of it, from a reader's tip
checked against published imagery. For those runs its `scripts/place_sources.py` rewrites
the starting locations of a copy of the input (one vertical line per magazine, same
heights), and the results are halved, because HYSPLIT gives each line the full emission
rate. The inputs here are not changed.

The fixed dry deposition speeds are the tracker's values at its 5 m/s reference wind (the
back-test's "Method"); they are the same on every day, while the tracker itself varies them
with the hourly wind.

## Running

```bash
export HYSPLIT_DIR=/path/to/hysplit.v5.4.2   # holds exec/hycs_std and bdyfiles/
./run_blast_day.sh early   # waits for the first file, then a 2-hour run
./run_blast_day.sh full    # waits for both, then the two 8-hour runs in parallel
```

`fetch` only downloads. Downloads go to `work/` (git-ignored); each run writes
`work/<name>/cdump`. Each back-test run took about 10 minutes on one CPU for 5 hours.

HYSPLIT itself is not in the repository (its licence restricts redistribution); get the
Linux build from https://www.ready.noaa.gov/HYSPLIT_linux.php. NOAA's READY site refused
connections from the cloud session that prepared this folder, so HYSPLIT has to be
installed where READY is reachable.
