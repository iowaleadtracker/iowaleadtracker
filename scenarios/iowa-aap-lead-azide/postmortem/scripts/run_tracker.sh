#!/usr/bin/env bash
# Rerun the tracker on HRRR's analyzed hours, and the sensitivity variants.
#
#   scripts/run_tracker.sh OUT_DIR            (from the repository root)
#
# Uses the weather saved in data/met_hrrr_asof_20261125_1856Z.json: Open-Meteo's HRRR
# as served at 12:56 p.m. CST on Nov. 25, when the hours through noon had been run
# and later hours were forecasts from the newest run. No network is used. Settings are
# the site's (make_map_picker.py MODEL_ARGS), with HRRR only and no deposition spread.
set -euo pipefail
OUT=${1:?output folder}
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$OUT"
run() {
  local name=$1; shift
  PUFF_MET_CACHE_ONLY=1 python3 puff_dispersal.py --lat 40.825518 --lon -91.266502 \
    --time 2026-11-25T09:00-06:00 --material lead-azide --explosive-mass 9700lb \
    --specific-energy 1.64 --shots 2 --confinement earth-covered --land-use crops \
    --spread turbulence --hours 8 --dt 60 --grid 360 --scale-min 0.15ug --decades 4 \
    --weather-model ncep_hrrr_conus --as-of 2026-11-25T18:56:01+00:00 \
    --met-cache "$HERE/../data/met_hrrr_asof_20261125_1856Z.json" "$@" -o "$OUT/$name.html" 2>&1 |
    grep -E "Error|Traceback" || true
}
run an_low --release-case ap42-floor
run an_mid --release-case army-26
run an_permit --release-case permit-100
# Sensitivity, 26% airborne: sizes, deposition and cloud height
run an_mid_mixed --airborne-fraction 0.26 --size-preset mixed
run an_mid_soil --airborne-fraction 0.26 --size-preset soil-bound
run an_mid_half --airborne-fraction 0.26 --respirable-fraction 0.5
run an_mid_vd1 --release-case army-26 --vd-extra 0.01
run an_mid_emerson --release-case army-26 --deposition emerson
run an_mid_low_cloud --release-case army-26 --church-factor 0.3
