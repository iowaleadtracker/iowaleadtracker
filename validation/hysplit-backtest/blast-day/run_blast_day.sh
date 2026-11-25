#!/usr/bin/env bash
# Fetch NOAA ARL's archived HRRR for the Nov. 25, 2026 blast (9 a.m. CST = 15 UTC)
# and run HYSPLIT on it. See README.md in this folder.
#
#   ./run_blast_day.sh fetch      wait for and download the two HRRR files
#   ./run_blast_day.sh early      2-hour run (15-17 UTC) once the first file is posted
#   ./run_blast_day.sh full       8-hour runs (Zhang and Emerson speeds)
#   ./run_blast_day.sh nowcast    runs on the hourly analyses nowcast_hrrr.sh builds
#
# Needs HYSPLIT (hycs_std) and its bdyfiles: set HYSPLIT_DIR to the unpacked
# distribution (the folder holding exec/ and bdyfiles/). WORK defaults to ./work.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
WORK=${WORK:-$HERE/work}
BUCKET=https://noaa-oar-arl-hysplit-pds.s3.amazonaws.com/hrrr/2026/11
FILES=(20261125_12-17_hrrr 20261125_18-23_hrrr)
mkdir -p "$WORK"

posted() { curl -sfI "$BUCKET/$1" >/dev/null; }

fetch() {  # wait until posted (checks every 5 min), then download and check the size
  local f=$1
  until posted "$f"; do echo "$(date -u +%H:%MZ) $f not posted yet"; sleep 300; done
  local want; want=$(curl -sfI "$BUCKET/$f" | tr -d '\r' | awk 'tolower($1)=="content-length:"{print $2}')
  if [[ -f $WORK/$f && $(stat -c %s "$WORK/$f") == "$want" ]]; then echo "$f already here"; return; fi
  echo "downloading $f ($want bytes)"
  curl -fL --retry 5 -C - -o "$WORK/$f" "$BUCKET/$f"
  [[ $(stat -c %s "$WORK/$f") == "$want" ]] || { echo "size mismatch for $f" >&2; exit 1; }
}

run() {  # run <name>: one HYSPLIT run in its own folder
  local name=$1 dir=$WORK/$1
  : "${HYSPLIT_DIR:?set HYSPLIT_DIR to the HYSPLIT distribution folder}"
  mkdir -p "$dir"
  cp "$HERE/$name.CONTROL" "$dir/CONTROL"
  cp "$HERE/SETUP.CFG" "$dir/"
  for f in ASCDATA.CFG LANDUSE.ASC ROUGLEN.ASC; do ln -sf "$HYSPLIT_DIR/bdyfiles/$f" "$dir/$f"; done
  for f in "${FILES[@]}" hrrr_nowcast_20261125.arl; do
    if [[ -f $WORK/$f ]]; then ln -sf "$WORK/$f" "$dir/$f"; fi
  done
  (cd "$dir" && "$HYSPLIT_DIR/exec/hycs_std" > hycs_std.log 2>&1) && echo "$name: $dir/cdump"
}

case ${1:-} in
  fetch) for f in "${FILES[@]}"; do fetch "$f"; done ;;
  early) fetch "${FILES[0]}"; run 2026-11-25-9am-zhang-early2h ;;
  full)  for f in "${FILES[@]}"; do fetch "$f"; done
         run 2026-11-25-9am-zhang & run 2026-11-25-9am-emerson & wait ;;
  nowcast) run 2026-11-25-9am-zhang-analyses & run 2026-11-25-9am-emerson-analyses & wait ;;
  *) sed -n 2,12p "$0"; exit 2 ;;
esac
