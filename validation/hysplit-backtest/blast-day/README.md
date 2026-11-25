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
| `20261125_18-23_hrrr` | noon–5 p.m. | about 6:40 p.m. Wed (latest seen: 7:00) | the 5-hour back-test length and the site's 8 hours |

Each file is 3.4 GB; from S3 one took about 2½ minutes here.

## Faster: raw HRRR (9 a.m. data by about 10:52 a.m.)

NOAA's raw HRRR on AWS (`noaa-hrrr-bdp-pds`) posts each hour's analysis about 51 minutes
after the hour (Nov. 25: 13Z at 13:51, 14Z at 14:51 UTC). The first 15 minutes after the
blast (15:00–15:15 UTC) need the 15Z and 16Z analyses, so a run is possible from about
**10:52 a.m. CST**, almost two hours before ARL's file.

`nowcast_hrrr.sh 15 16` waits for those analyses (`wrfprsf00`, pressure levels), converts
each with HYSPLIT's `api2arl_v4` (about 20 s, 550 MB per hour, full 3 km grid, 1013–50 hPa)
and appends it to `work/hrrr_nowcast_20261125.arl`. Give later hours (e.g. `17 23`) to
extend it. `./run_blast_day.sh nowcast` then runs the two `*-nowcast1h` inputs (9–10 a.m.).

This is not the same weather input as ARL's archive: pressure levels every 25 hPa instead
of HRRR's native levels, and analyses without surface fluxes (HYSPLIT then estimates
stability from the temperature and wind profile). Treat it as preliminary and rerun on
ARL's file when it is posted. `api2arl_v4` needs ecCodes (`apt-get install libeccodes0`).

## Runs

| CONTROL | Hours | Deposition speeds |
|---|---|---|
| `2026-11-25-9am-zhang-early2h` | 2 | Zhang |
| `2026-11-25-9am-zhang` | 8 | Zhang |
| `2026-11-25-9am-emerson` | 8 | Emerson |

Made from the back-test's Monday (overcast) inputs. Changed: start `26 11 25 15 00`,
the two met files, and a grid centred on the plant spanning 3° × 4° (about 330 × 340 km)
since the wind direction is not known in advance. Release, particle sizes, output levels
(0, 0–10 m, 0–100 m) and `SETUP.CFG` (200,000 particles) are as in the back-test.

**Check before comparing:** the fixed dry deposition speeds are Monday's, taken from our
model's map for that day. For a like-for-like comparison, replace them with the speeds our
model reports for the blast-day run (the back-test's "Method").

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
