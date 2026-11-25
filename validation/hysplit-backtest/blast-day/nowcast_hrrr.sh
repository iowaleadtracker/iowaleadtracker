#!/usr/bin/env bash
# Build an ARL weather file for the blast from NOAA's raw HRRR analyses on AWS,
# hours before NOAA ARL's own archive file is posted. See README.md, "Faster: raw HRRR".
#
#   ./nowcast_hrrr.sh [FIRST_HOUR_UTC] [LAST_HOUR_UTC]     default 15 23
#
# For each hour it waits for hrrr.tHHz.wrfprsf00.grib2 (the analysis on pressure
# levels, posted about 51 minutes after the hour), converts it with HYSPLIT's
# api2arl_v4 and appends it to $WORK/hrrr_nowcast_20261125.arl. Needs HYSPLIT_DIR
# (exec/api2arl_v4) and the ecCodes library (Ubuntu: apt-get install libeccodes0).
set -euo pipefail
: "${HYSPLIT_DIR:?set HYSPLIT_DIR to the HYSPLIT distribution folder}"
HERE=$(cd "$(dirname "$0")" && pwd)
WORK=${WORK:-$HERE/work}
DAY=20261125
SRC=https://noaa-hrrr-bdp-pds.s3.amazonaws.com/hrrr.$DAY/conus
OUT=$WORK/hrrr_nowcast_$DAY.arl
first=${1:-15} last=${2:-23}
mkdir -p "$WORK/nowcast" && cd "$WORK/nowcast"

for ((h = 10#$first; h <= 10#$last; h++)); do
  hh=$(printf %02d "$h")
  if [[ -f done_$hh ]]; then echo "${hh}Z already in $OUT"; continue; fi
  url=$SRC/hrrr.t${hh}z.wrfprsf00.grib2
  until curl -sfI "$url" >/dev/null; do echo "$(date -u +%H:%MZ) ${hh}Z analysis not posted yet"; sleep 120; done
  sleep 60  # let the upload settle
  curl -sfL --retry 5 -o in.grib2 "$url"
  if [[ ! -f $OUT ]]; then
    rm -f arldata.cfg  # first hour defines the record layout; later hours reuse it
    "$HYSPLIT_DIR/exec/api2arl_v4" -iin.grib2 -oDATA.ARL -gHRRR -t50 > "api2arl_$hh.log" 2>&1
  else
    "$HYSPLIT_DIR/exec/api2arl_v4" -earldata.cfg -iin.grib2 -oDATA.ARL -gHRRR -t50 > "api2arl_$hh.log" 2>&1
  fi
  grep -q "Finished:.*$h" "api2arl_$hh.log" || { echo "conversion of ${hh}Z failed; see api2arl_$hh.log" >&2; exit 1; }
  cat DATA.ARL >> "$OUT" && rm -f DATA.ARL in.grib2 && touch "done_$hh"
  echo "$(date -u +%H:%MZ) added ${hh}Z to $OUT"
done
