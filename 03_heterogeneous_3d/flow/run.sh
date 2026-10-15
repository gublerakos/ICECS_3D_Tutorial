#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/config.sh"
export ROOT
export FULL_TOP_LEF="$TOP_LEF"
export REFERENCE_NETLIST="${REFERENCE_NETLIST:-$ROOT/data/cva6_bottom_reference.v}"
export SDC_FILE="${SDC_FILE:-$(dirname "$REFERENCE_NETLIST")/cva6.sdc}"
export RUN_DIR="${RUN_DIR:-$ROOT/runs/cva6_45nm_top_15nm_bottom}"
export OPENROAD_BIN="${OPENROAD_BIN:-openroad}"
export THREADS="${THREADS:-24}"
export TECH_LEF="${TECH_LEF:-$ROOT/pdk/nangate_tech.lef}"
export FLOORPLAN_UTILIZATION="${FLOORPLAN_UTILIZATION:-70}"
export TARGET_UTILIZATION="${TARGET_UTILIZATION:-0.70}"
export GP_DENSITY="${GP_DENSITY:-0.70}"
export CAPACITY_BASIS="${CAPACITY_BASIS:-virtual}"
export TOP_GP_HEIGHT="${TOP_GP_HEIGHT:-0.700}"
export TOP_DP_HEIGHT="${TOP_DP_HEIGHT:-0.466}"
export VIRTUAL_ROW_HEIGHT="${VIRTUAL_ROW_HEIGHT:-0.466}"
export ROUTING_GUARD_BAND_ROWS="${ROUTING_GUARD_BAND_ROWS:-1}"
export DP_MAX_DISPLACEMENT="${DP_MAX_DISPLACEMENT:-3000}"
export ORIENTATION_PATTERN="${ORIENTATION_PATTERN:-N,N,FS,N,FS,FS}"
export SIGNAL_ROUTING_LAYERS="${SIGNAL_ROUTING_LAYERS:-metal1_bottom_tier-metal6_bottom_tier}"
export CLOCK_ROUTING_LAYERS="${CLOCK_ROUTING_LAYERS:-$SIGNAL_ROUTING_LAYERS}"
usage() {
  echo "Usage: $0 check|prepare|generate|place VERSION|place-all|route VERSION|route-all|gui VERSION"
  echo "Versions: v2 v3 v4 v5. Default: prepare (partition and generate LEFs; no OpenROAD)."
  echo "Use a new absolute RUN_DIR for a different configuration."
}
action="${1:-prepare}"
case "$action" in
  -h|--help|help) usage; exit 0 ;;
  check|prepare|generate|place-all|route-all) [[ $# -le 1 ]] || { usage; exit 2; } ;;
  place|route|gui) [[ $# -eq 2 && "$2" =~ ^v[2345]$ ]] || { usage; exit 2; } ;;
  *) usage; exit 2 ;;
esac
[[ "$RUN_DIR" = /* ]] || { echo 'RUN_DIR must be absolute' >&2; exit 2; }
for path in "$REFERENCE_NETLIST" "$SDC_FILE" "$TOP_LIBERTY" "$BOTTOM_LIBERTY" "$FULL_TOP_LEF" "$BOTTOM_LEF" "$TECH_LEF"; do
  [[ -f "$path" ]] || { echo "Missing input: $path" >&2; exit 1; }
done
command -v "$OPENROAD_BIN" >/dev/null 2>&1 || { echo "Missing OpenROAD executable: $OPENROAD_BIN" >&2; exit 1; }
if [[ "$action" = check ]]; then
  python3 "$HERE/prepare.py" --check
  exit
fi
mkdir -p "$RUN_DIR"
exec 9>"$RUN_DIR/run.lock"
flock -n 9 || { echo "Another command is using $RUN_DIR" >&2; exit 1; }
python3 "$HERE/prepare.py"
[[ "$action" != prepare ]] || exit 0
export BASE_OUT="$RUN_DIR/initial"
export V5_NETLIST="$RUN_DIR/partition/cva6_heterogeneous.v"
export BOTTOM_LIB="$RUN_DIR/partition/bottom_15nm.lib"
export TOP_LIB="$TOP_LIBERTY"
export OUTPUT_TAG=cva6_util70_virtualrow
export SDC_FILE="$RUN_DIR/cva6.sdc"
exec bash "$HERE/placement.sh" "$@"
