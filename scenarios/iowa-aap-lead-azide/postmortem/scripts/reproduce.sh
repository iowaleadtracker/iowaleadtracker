#!/usr/bin/env bash
# Rebuild every number and figure in the first comparison.
#
#   HYSPLIT_DIR=/path/to/hysplit scenarios/iowa-aap-lead-azide/postmortem/scripts/reproduce.sh WORK
#
# Run from the repository root. WORK is a scratch folder; steps whose outputs are already
# there are skipped. Needs HYSPLIT 5.4.2 with ecCodes (for the weather conversion), and
# the packages in requirements.txt plus matplotlib, scipy and Pillow. FETCH_EPA=1 downloads
# EPA's layers again instead of using the copy in data/epa.
set -euo pipefail
: "${HYSPLIT_DIR:?set HYSPLIT_DIR to the HYSPLIT distribution folder}"
WORK=$(mkdir -p "${1:?work folder}" && cd "$1" && pwd)
P=scenarios/iowa-aap-lead-azide/postmortem
BD=validation/hysplit-backtest/blast-day
FORECAST_COMMIT=c9f8e59   # the forecast the site showed at 9 a.m. (pulled 8:36 a.m. CST)
ARL=hrrr_nowcast_20261125.arl

# 1. The site's maps from the forecast it showed at 9 a.m.
if [[ ! -d $WORK/forecast ]]; then
  git worktree add "$WORK/forecast" "$FORECAST_COMMIT"
  (cd "$WORK/forecast" && python3 scenarios/iowa-aap-lead-azide/make_map_picker.py --build)
fi
FC=$WORK/forecast/scenarios/iowa-aap-lead-azide/outputs/site/maps

# 2. The tracker on analyzed weather, and the sensitivity runs (no network)
[[ -f $WORK/maps/an_mid_low_cloud.html ]] || "$P/scripts/run_tracker.sh" "$WORK/maps"

# 3. HYSPLIT, 9 a.m. to 5 p.m. Reference runs: NOAA ARL's archived HRRR on native levels.
#    Sensitivity run: the raw hourly analyses on pressure levels.
ARCHIVE=(20261125_12-17_hrrr 20261125_18-23_hrrr)
for f in "${ARCHIVE[@]}"; do
  [[ -f $WORK/$f ]] || curl -fL --retry 5 -C - -o "$WORK/$f" \
    "https://noaa-oar-arl-hysplit-pds.s3.amazonaws.com/hrrr/2026/11/$f"
done
[[ -f $WORK/$ARL ]] || WORK=$WORK "$BD/nowcast_hrrr.sh" 15 23
hysplit() {  # hysplit RUN_NAME CONTROL_NAME WEATHER_FILE...
  local r=$WORK/$1
  [[ -s $r/cdump ]] && return
  mkdir -p "$r"
  cp "$BD/$2.CONTROL" "$r/CONTROL"
  cp "$BD/SETUP.CFG" "$r/"
  for f in ASCDATA.CFG LANDUSE.ASC ROUGLEN.ASC; do ln -sf "$HYSPLIT_DIR/bdyfiles/$f" "$r/$f"; done
  for f in "${@:3}"; do ln -sf "$WORK/$f" "$r/$f"; done
  (cd "$r" && "$HYSPLIT_DIR/exec/hycs_std" > hycs_std.log 2>&1)
}
hysplit run_arl_zhang 2026-11-25-9am-zhang "${ARCHIVE[@]}" &
hysplit run_arl_emerson 2026-11-25-9am-emerson "${ARCHIVE[@]}" &
hysplit run_analyses_zhang 2026-11-25-9am-zhang-analyses "$ARL" &
hysplit run_arl_coarse 2026-11-25-9am-coarse-early2h "${ARCHIVE[0]}" &  # coarse sizes, 2 hours
hysplit run_arl_lofted 2026-11-25-9am-zhang-lofted "${ARCHIVE[@]}" &  # released at 251-502 m, 4 hours
wait

# 4. EPA's public layers
if [[ ${FETCH_EPA:-0} == 1 ]]; then python3 "$P/scripts/epa_fetch.py" "$P/data/epa"; fi

# 5. Numbers
cache=$WORK/forecast/scenarios/iowa-aap-lead-azide/met_cache/map_met_all.json
(cd "$P/scripts" && python3 compare.py "$FC" "$WORK/maps" "$WORK/run_arl_zhang" "$WORK/run_arl_emerson" \
  "$WORK/run_analyses_zhang" ../data/epa) > "$P/data/compare.json"
(cd "$P/scripts" && python3 army_map.py ../data/army "$FC/mid-0900.html" "$WORK/maps/an_mid.html") > "$P/data/army_map.json"
python3 "$P/scripts/forecast_vs_analysis.py" "$cache" "$WORK" "$ARL" > "$P/data/forecast_vs_analysis.json"
python3 "$P/scripts/station_vs_hrrr.py" "$WORK" "$ARL" "$P/data/obs" > "$P/data/station_vs_hrrr.json"
(cd "$P/scripts" && python3 monitor_coverage.py "$FC" "$WORK/maps" "$WORK/run_arl_zhang" ../data/epa "$WORK/run_arl_lofted") > "$P/data/monitor_coverage.json"
AN_CACHE=$(ls "$PWD/$P"/data/met_hrrr_asof_*.json)
(cd "$P/scripts" && python3 coarse.py "$AN_CACHE" ../data/epa "$WORK/run_arl_coarse") > "$P/data/coarse.json"
(cd "$P/scripts" && python3 snapshots.py "$cache" "$AN_CACHE" "$WORK/run_arl_zhang" "$WORK/run_analyses_zhang") > "$P/data/snapshots.json"

# 6. Figures
(cd "$P/scripts" && python3 figure.py "$FC" "$WORK/maps" "$WORK/run_arl_zhang" ../data/army ../data/epa \
  ../data/monitor_coverage.json "$cache" "$AN_CACHE" ../figures)
# 7. Tables in README.md
python3 "$P/scripts/tables.py"
echo "done: $P/data, $P/figures, tables in $P/README.md"
