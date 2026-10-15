#!/bin/bash
set -euo pipefail

# Internal CVA6 adapter for the VGA v5 wrapper. Invoke through run.sh.
: "${RUN_DIR:?Use run.sh}" "${SDC_FILE:?Use run.sh}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OPENROAD_BIN="${OPENROAD_BIN:-openroad}"
SCRIPTS_PATH="$ROOT/tcl_scripts"
PYTHON_PATH="$ROOT/python_scripts"
LEF_HEIGHT_GEN="$PYTHON_PATH/make_dp_rowheight_lef.py"
LEF_LAYER_MAP="$PYTHON_PATH/map_lef_layers.py"

LIBS_PATH="${LIBS_PATH:-$ROOT/pdk}"
TECH_LEF="${TECH_LEF:-$LIBS_PATH/nangate_tech.lef}"
BOTTOM_LEF="${BOTTOM_LEF:-$LIBS_PATH/nangate_stdcell_bottom_tier.lef}"
FULL_TOP_LEF="${FULL_TOP_LEF:-$ROOT/pdk/nangate_stdcell_top_tier.lef}"
BOTTOM_LIB="${BOTTOM_LIB:?Use run.sh to prepare the clean bottom Liberty}"
TOP_LIB="${TOP_LIB:-$LIBS_PATH/nangate_typical_top_tier.lib}"
V5_NETLIST="${V5_NETLIST:?Use run.sh to prepare the partitioned netlist}"
FLOORPLAN_UTILIZATION="${FLOORPLAN_UTILIZATION:-70}"
TARGET_UTILIZATION="${TARGET_UTILIZATION:-0.70}"
CAPACITY_BASIS="${CAPACITY_BASIS:-virtual}"
TOP_GP_HEIGHT="${TOP_GP_HEIGHT:-0.700}"
TOP_DP_HEIGHT="${TOP_DP_HEIGHT:-0.466}"
VIRTUAL_ROW_HEIGHT="${VIRTUAL_ROW_HEIGHT:-$TOP_DP_HEIGHT}"
ROUTING_GUARD_BAND_ROWS="${ROUTING_GUARD_BAND_ROWS:-1}"
SIGNAL_ROUTING_LAYERS="${SIGNAL_ROUTING_LAYERS:-metal1_bottom_tier-metal6_bottom_tier}"
CLOCK_ROUTING_LAYERS="${CLOCK_ROUTING_LAYERS:-$SIGNAL_ROUTING_LAYERS}"

BASE_OUT="${BASE_OUT:-./outputs_v5net_util70_virtualrow_initial}"
LEF_TEST_DIR="${LEF_TEST_DIR:-$BASE_OUT/lef_test}"
TOP_GP_LEF="${TOP_GP_LEF:-$LEF_TEST_DIR/nangate_stdcell_top_tier_gp_macroheight_0p700_site_0p466.lef}"
TOP_DP_LEF="${TOP_DP_LEF:-$LEF_TEST_DIR/nangate_stdcell_top_tier_dp_macroheight_0p466_site_0p466.lef}"
TOP_ROUTE_LEF="${TOP_ROUTE_LEF:-$LEF_TEST_DIR/nangate_stdcell_top_tier_route_bottom_layers_0p466.lef}"
INITIAL_TCL="$BASE_OUT/create_initial_def_v5net.tcl"
INITIAL_DEF="$BASE_OUT/defs/final/inital_def.def"
INITIAL_LOG="$BASE_OUT/logs/openroad_initial_v5net.log"

ACTION="${1:-generate}"
if [ $# -gt 0 ]; then
  shift
fi

for path in "$TECH_LEF" "$BOTTOM_LEF" "$FULL_TOP_LEF" "$BOTTOM_LIB" "$TOP_LIB" "$V5_NETLIST" "$LEF_HEIGHT_GEN" "$LEF_LAYER_MAP"; do
  if [ ! -f "$path" ]; then
    echo "Missing required input: $path" >&2
    exit 1
  fi
done

mkdir -p "$BASE_OUT/defs/final" "$BASE_OUT/logs" "$LEF_TEST_DIR"

make_top_lef() {
  local output_lef="$1"
  local target_height="$2"
  local label="$3"

  if [ -e "$output_lef" ]; then
    echo "Keeping existing $label top LEF: $output_lef"
    return 0
  fi

  python3 "$LEF_HEIGHT_GEN" \
    --input-lef "$FULL_TOP_LEF" \
    --output-lef "$output_lef" \
    --target-height "$target_height" \
    --site-height "$VIRTUAL_ROW_HEIGHT"
}

make_top_lef "$TOP_GP_LEF" "$TOP_GP_HEIGHT" "GP half-height"
make_top_lef "$TOP_DP_LEF" "$TOP_DP_HEIGHT" "DP row-height"

if [ -e "$TOP_ROUTE_LEF" ]; then
  echo "Keeping existing route-eval top LEF: $TOP_ROUTE_LEF"
else
  python3 "$LEF_LAYER_MAP" \
    --input-lef "$TOP_DP_LEF" \
    --output-lef "$TOP_ROUTE_LEF" \
    --map metal1_top_tier=metal1_bottom_tier
fi

if [ ! -f "$INITIAL_TCL" ]; then
  cat > "$INITIAL_TCL" <<EOL
set scripts_path "$SCRIPTS_PATH"
set outputs_path "$BASE_OUT"

set_thread_count ${THREADS:-24}

source "\$scripts_path/flow_helpers.tcl"

set platform "nangate45"
set tech_lef "$TECH_LEF"
set std_cell_lef "$BOTTOM_LEF"
set liberty_file "$BOTTOM_LIB"
set extra_lef "$TOP_GP_LEF"
set extra_liberty "$TOP_LIB"

read_libraries

set design "cva6"
set top_module "cva6"
set synth_verilog "$V5_NETLIST"
set site "NanGate_15nm_OCL"

read_verilog \$synth_verilog
link_design \$top_module
read_sdc "$SDC_FILE"

initialize_floorplan -utilization $FLOORPLAN_UTILIZATION -aspect_ratio 1 -core_space 0 -site \$site
write_def $INITIAL_DEF
exit
EOL
else
  echo "Keeping existing initial DEF TCL: $INITIAL_TCL"
  if ! grep -q -- "-utilization $FLOORPLAN_UTILIZATION\\b" "$INITIAL_TCL"; then
    echo "Existing initial DEF TCL does not use FLOORPLAN_UTILIZATION=$FLOORPLAN_UTILIZATION: $INITIAL_TCL" >&2
    echo "Choose a new BASE_OUT or remove the stale generated util TCL/DEF." >&2
    exit 1
  fi
  if ! grep -Fq -- "set extra_lef \"$TOP_GP_LEF\"" "$INITIAL_TCL"; then
    echo "Existing initial DEF TCL does not use TOP_GP_LEF=$TOP_GP_LEF: $INITIAL_TCL" >&2
    echo "Choose a new BASE_OUT or remove the stale generated util TCL/DEF." >&2
    exit 1
  fi
fi

if [ ! -f "$INITIAL_DEF" ]; then
  if [ -e "$INITIAL_LOG" ]; then
    archived_log="$(mktemp "${INITIAL_LOG}.previous.XXXXXX")"
    mv "$INITIAL_LOG" "$archived_log"
    echo "Preserved previous incomplete initial-floorplan log: $archived_log"
  fi
  "$OPENROAD_BIN" -no_init -no_splash -exit -log "$INITIAL_LOG" "$INITIAL_TCL"
else
  echo "Keeping existing initial DEF: $INITIAL_DEF"
fi

export OPENROAD_BIN
export INITIAL_DEF
export OUTPUT_TAG="${OUTPUT_TAG:-v5net_util70_virtualrow}"
export SYNTH_VERILOG="$V5_NETLIST"
export TECH_LEF
export BOTTOM_LEF
export TOP_LEF="$TOP_GP_LEF"
export TOP_DP_LEF
export TOP_ROUTE_LEF
export TOP_GOLDEN_LEF="$TOP_DP_LEF"
export BOTTOM_LIB
export TOP_LIB
export ROUTING_GUARD_BAND_ROWS
export SIGNAL_ROUTING_LAYERS
export CLOCK_ROUTING_LAYERS
export TARGET_UTILIZATION
export CAPACITY_BASIS
export GP_DENSITY="${GP_DENSITY:-0.70}"

exec bash "$SCRIPT_DIR/capacity_sweep.sh" "$ACTION" "$@"
