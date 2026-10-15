#!/bin/bash
set -euo pipefail
: "${RUN_DIR:?Use run.sh}" "${SDC_FILE:?Use run.sh}"

# Generate and optionally place compact BOTTOM/TOP/BOTTOM DEF variants.
# This script never writes into the original outputs/ flow products.
# Existing files are reused or left untouched; placement outputs refuse overwrite.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OPENROAD_BIN="${OPENROAD_BIN:-openroad}"
SCRIPTS_PATH="$ROOT/tcl_scripts"
PYTHON_PATH="$ROOT/python_scripts"
HETERO_GEN="$PYTHON_PATH/create_virtual_btb_floorplan.py"

# Shared initial DEF with overlapping top/bottom rows.
INITIAL_DEF="${INITIAL_DEF:-./outputs/defs/final/inital_def.def}"


LIBS_PATH="${LIBS_PATH:-$ROOT/pdk}"
TECH_LEF="${TECH_LEF:-$LIBS_PATH/nangate_tech.lef}"
BOTTOM_LEF="${BOTTOM_LEF:-$LIBS_PATH/nangate_stdcell_bottom_tier.lef}"
TOP_LEF="${TOP_LEF:-$ROOT/pdk/nangate_stdcell_top_tier.lef}"
TOP_DP_LEF="${TOP_DP_LEF:-${TOP_GOLDEN_LEF:-$TOP_LEF}}"
TOP_ROUTE_LEF="${TOP_ROUTE_LEF:-$TOP_DP_LEF}"
BOTTOM_LIB="${BOTTOM_LIB:-$LIBS_PATH/nangate_typical_bottom_tier.lib}"
TOP_LIB="${TOP_LIB:-$LIBS_PATH/nangate_typical_top_tier.lib}"
SYNTH_VERILOG="${SYNTH_VERILOG:?Use run.sh}"
TRACKS_FILE="$ROOT/pdk/Nangate45.tracks"
GP_DENSITY="${GP_DENSITY:-0.70}"
DP_MAX_DISPLACEMENT="${DP_MAX_DISPLACEMENT:-3000}"
ORIENTATION_PATTERN="${ORIENTATION_PATTERN:-N,N,FS,N,FS,FS}"
ROUTING_GUARD_BAND_ROWS="${ROUTING_GUARD_BAND_ROWS:-0}"
SIGNAL_ROUTING_LAYERS="${SIGNAL_ROUTING_LAYERS:-}"
CLOCK_ROUTING_LAYERS="${CLOCK_ROUTING_LAYERS:-$SIGNAL_ROUTING_LAYERS}"
TARGET_UTILIZATION="${TARGET_UTILIZATION:-0.70}"
CAPACITY_BASIS="${CAPACITY_BASIS:-virtual}"
OUTPUT_TAG="${OUTPUT_TAG:-}"

VERSIONS=("v2:1.0" "v3:1.2" "v4:1.3" "v5:1.5")

usage() {
  cat <<EOF
Usage:
  $0 generate           Generate compact DEFs, reports, and TCL files for v2-v5.
  $0 place <v2|v3|v4|v5>
                        Run OpenROAD GP + detailed placement for one version.
  $0 place-all          Run OpenROAD GP + detailed placement for all versions.
  $0 route <v2|v3|v4|v5>
                        Run global_route, optional detailed_route, and DRC checks.
  $0 route-all          Run routing evaluation for all versions.
  $0 gui <v2|v3|v4|v5>  Open the version in OpenROAD GUI.

Environment overrides:
  OPENROAD_BIN, INITIAL_DEF, OUTPUT_TAG, SYNTH_VERILOG,
  TECH_LEF, BOTTOM_LEF, TOP_LEF, TOP_DP_LEF, TOP_ROUTE_LEF, BOTTOM_LIB, TOP_LIB,
  GP_DENSITY, DP_MAX_DISPLACEMENT, ORIENTATION_PATTERN,
  ROUTING_GUARD_BAND_ROWS, SIGNAL_ROUTING_LAYERS, CLOCK_ROUTING_LAYERS,
  TARGET_UTILIZATION, CAPACITY_BASIS
EOF
}

version_scale() {
  local want="$1"
  local item version scale
  for item in "${VERSIONS[@]}"; do
    version="${item%%:*}"
    scale="${item##*:}"
    if [ "$version" = "$want" ]; then
      echo "$scale"
      return 0
    fi
  done
  return 1
}

version_dir() {
  if [ -n "$OUTPUT_TAG" ]; then
    echo "$RUN_DIR/outputs_${OUTPUT_TAG}_$1"
  else
    echo "$RUN_DIR/outputs_$1"
  fi
}

hetero_def() {
  echo "$(version_dir "$1")/defs/heterogeneous_compact_$1.def"
}

report_file() {
  echo "$(version_dir "$1")/reports/heterogeneous_compact_$1.rpt"
}

gp_tcl() {
  echo "$(version_dir "$1")/run_gp_compact_$1.tcl"
}

dp_tcl() {
  echo "$(version_dir "$1")/run_dp_compact_$1.tcl"
}

gui_tcl() {
  echo "$(version_dir "$1")/open_gui_compact_$1.tcl"
}

post_gp_def() {
  echo "$(version_dir "$1")/defs/postGP_compact_$1.def"
}

post_dp_def() {
  echo "$(version_dir "$1")/defs/postDP_compact_$1.def"
}

gp_log() {
  echo "$(version_dir "$1")/logs/openroad_gp_compact_$1.log"
}

dp_log() {
  echo "$(version_dir "$1")/logs/openroad_dp_compact_$1.log"
}

route_tcl() {
  echo "$(version_dir "$1")/run_route_compact_$1.tcl"
}

route_log() {
  echo "$(version_dir "$1")/logs/openroad_route_compact_$1.log"
}

route_guide() {
  echo "$(version_dir "$1")/routing/route_guide_compact_$1.guide"
}

congestion_report() {
  echo "$(version_dir "$1")/routing/congestion_compact_$1.rpt"
}

droute_drc_report() {
  echo "$(version_dir "$1")/routing/droute_drc_compact_$1.rpt"
}

check_drc_report() {
  echo "$(version_dir "$1")/routing/check_drc_compact_$1.rpt"
}

drc_summary() {
  echo "$(version_dir "$1")/routing/drc_summary_compact_$1.rpt"
}

routed_def() {
  echo "$(version_dir "$1")/defs/routed_compact_$1.def"
}

ensure_version() {
  if ! version_scale "$1" >/dev/null; then
    echo "Unknown version: $1" >&2
    usage >&2
    exit 1
  fi
}

write_once() {
  local path="$1"
  if [ -e "$path" ]; then
    echo "Keeping existing file: $path"
    return 1
  fi
  mkdir -p "$(dirname "$path")"
  return 0
}

ensure_absent() {
  local path="$1"
  if [ -e "$path" ]; then
    echo "Refusing to overwrite existing file: $path" >&2
    exit 1
  fi
}

generate_one() {
  local version="$1"
  local scale
  scale="$(version_scale "$version")"
  local dir def report
  dir="$(version_dir "$version")"
  def="$(hetero_def "$version")"
  report="$(report_file "$version")"

  mkdir -p "$dir/defs" "$dir/reports" "$dir/logs"

  if [ -e "$def" ]; then
    echo "Keeping existing DEF: $def"
  else
    python3 "$HETERO_GEN" \
      --input-def "$INITIAL_DEF" \
      --output-def "$def" \
      --lef "$BOTTOM_LEF" \
      --lef "$TOP_LEF" \
      --utilization "$TARGET_UTILIZATION" \
      --capacity-basis "$CAPACITY_BASIS" \
      --capacity-scale "$scale" \
      --orientation-pattern "$ORIENTATION_PATTERN" \
      --routing-guard-band-rows "$ROUTING_GUARD_BAND_ROWS" \
      --version-label "$version" \
      --report-file "$report"
  fi

  make_gp_tcl "$version"
  make_dp_tcl "$version"
  make_gui_tcl "$version"
  make_route_tcl "$version"
}

make_gp_tcl() {
  local version="$1"
  local path
  path="$(gp_tcl "$version")"
  write_once "$path" || return 0
  cat > "$path" <<EOL
set scripts_path "$SCRIPTS_PATH"
set outputs_path "$(version_dir "$version")"

set_thread_count ${THREADS:-24}

source "\$scripts_path/flow_helpers.tcl"

set platform "nangate45"
set tech_lef "$TECH_LEF"
set std_cell_lef "$BOTTOM_LEF"
set liberty_file "$BOTTOM_LIB"
set extra_lef "$TOP_LEF"
set extra_liberty "$TOP_LIB"

read_libraries

set design "cva6"
set top_module "cva6"
set synth_verilog "$SYNTH_VERILOG"
set tracks_file "$TRACKS_FILE"
set io_placer_hor_layer metal2_bottom_tier
set io_placer_ver_layer metal1_bottom_tier

read_def $(hetero_def "$version")
read_verilog \$synth_verilog
read_sdc "$SDC_FILE"
source \$tracks_file
place_pins -ver_layers \$io_placer_ver_layer -hor_layers \$io_placer_hor_layer

global_placement -density $GP_DENSITY
write_def "$(post_gp_def "$version").tmp"
file rename -force -- "$(post_gp_def "$version").tmp" "$(post_gp_def "$version")"
exit
EOL
}

make_dp_tcl() {
  local version="$1"
  local path
  path="$(dp_tcl "$version")"
  write_once "$path" || return 0
  cat > "$path" <<EOL
set scripts_path "$SCRIPTS_PATH"
source "\$scripts_path/flow_helpers.tcl"

set_thread_count ${THREADS:-24}

set tech_lef "$TECH_LEF"
set std_cell_lef "$BOTTOM_LEF"
set liberty_file "$BOTTOM_LIB"
set extra_lef "$TOP_DP_LEF"
set extra_liberty "$TOP_LIB"

read_libraries

read_def $(post_gp_def "$version")
read_verilog "$SYNTH_VERILOG"
read_sdc "$SDC_FILE"

puts "Starting detailed placement"
flush stdout
detailed_placement -max_displacement $DP_MAX_DISPLACEMENT
check_placement -verbose
write_def "$(post_dp_def "$version").tmp"
file rename -force -- "$(post_dp_def "$version").tmp" "$(post_dp_def "$version")"
exit
EOL
}

make_gui_tcl() {
  local version="$1"
  local path
  path="$(gui_tcl "$version")"
  write_once "$path" || return 0
  cat > "$path" <<EOL
set scripts_path "$SCRIPTS_PATH"
source "\$scripts_path/flow_helpers.tcl"

set_thread_count ${THREADS:-24}

set tech_lef "$TECH_LEF"
set std_cell_lef "$BOTTOM_LEF"
set liberty_file "$BOTTOM_LIB"
set extra_lef "$TOP_DP_LEF"
set extra_liberty "$TOP_LIB"

read_libraries

if {[file exists "$(post_dp_def "$version")"]} {
  read_def $(post_dp_def "$version")
} else {
  read_def $(post_gp_def "$version")
}
read_verilog "$SYNTH_VERILOG"
read_sdc "$SDC_FILE"
gui::show
EOL
}

make_route_tcl() {
  local version="$1"
  local path
  path="$(route_tcl "$version")"
  write_once "$path" || return 0
  cat > "$path" <<EOL
set scripts_path "$SCRIPTS_PATH"
source "\$scripts_path/flow_helpers.tcl"

set_thread_count ${THREADS:-24}

set tech_lef "$TECH_LEF"
set std_cell_lef "$BOTTOM_LEF"
set liberty_file "$BOTTOM_LIB"
set extra_lef "$TOP_ROUTE_LEF"
set extra_liberty "$TOP_LIB"

read_libraries

read_def $(post_dp_def "$version")
read_verilog "$SYNTH_VERILOG"
read_sdc "$SDC_FILE"
source $TRACKS_FILE

if {"$SIGNAL_ROUTING_LAYERS" ne ""} {
  set_routing_layers -signal $SIGNAL_ROUTING_LAYERS -clock $CLOCK_ROUTING_LAYERS
}

set route_guide "$(route_guide "$version")"
set congestion_report "$(congestion_report "$version")"
set droute_drc "$(droute_drc_report "$version")"
set check_drc_report "$(check_drc_report "$version")"
set drc_summary "$(drc_summary "$version")"
set routed_def "$(routed_def "$version")"

global_route \\
  -guide_file \$route_guide \\
  -congestion_iterations 100 \\
  -congestion_report_file \$congestion_report \\
  -verbose

set detailed_route_status [catch {
  detailed_route -output_drc \$droute_drc -verbose 1
} detailed_route_msg]

if {\$detailed_route_status == 0} {
  set check_drc_status [catch {
    check_drc -output_file \$check_drc_report
  } check_drc_msg]
} else {
  set check_drc_status "SKIPPED"
  set check_drc_msg "detailed_route failed; check_drc not run"
}

set drc_count "UNKNOWN"
if {\$detailed_route_status == 0 && [info commands detailed_route_num_drvs] ne ""} {
  set drc_count [detailed_route_num_drvs]
}

set fp [open \$drc_summary w]
puts \$fp "version: $version"
puts \$fp "global_route_status: 0"
puts \$fp "route_guide: \$route_guide"
puts \$fp "congestion_report: \$congestion_report"
puts \$fp "detailed_route_status: \$detailed_route_status"
puts \$fp "detailed_route_message: \$detailed_route_msg"
puts \$fp "droute_drc_report: \$droute_drc"
puts \$fp "check_drc_status: \$check_drc_status"
puts \$fp "check_drc_message: \$check_drc_msg"
puts \$fp "check_drc_report: \$check_drc_report"
puts \$fp "drc_count: \$drc_count"
close \$fp

if {\$detailed_route_status == 0} {
  write_def \$routed_def
}

exit 0
EOL
}

generate_all() {
  if [ ! -f "$INITIAL_DEF" ]; then
    echo "Missing shared initial DEF: $INITIAL_DEF" >&2
    echo "Run the original initial DEF generation first or set INITIAL_DEF=/path/to/inital_def.def." >&2
    exit 1
  fi
  local item version
  for item in "${VERSIONS[@]}"; do
    version="${item%%:*}"
    generate_one "$version"
  done
}

place_one() {
  local version="$1"
  ensure_version "$version"
  generate_one "$version"
  ensure_absent "$(post_dp_def "$version")"
  if [ ! -f "$(post_gp_def "$version")" ]; then
    echo "[1/2] Global placement: $version"
  "$OPENROAD_BIN" -no_init -no_splash -exit -log "$(gp_log "$version")" "$(gp_tcl "$version")"
  else
    echo "[1/2] Reusing completed GP DEF: $(post_gp_def "$version")"
  fi
  echo "[2/2] Detailed placement: $version (large designs may be quiet for many minutes)"
  "$OPENROAD_BIN" -no_init -no_splash -exit -log "$(dp_log "$version")" "$(dp_tcl "$version")"
  echo "Placed $version"
  echo "  GP DEF: $(post_gp_def "$version")"
  echo "  DP DEF: $(post_dp_def "$version")"
  echo "  GP log: $(gp_log "$version")"
  echo "  DP log: $(dp_log "$version")"
}

place_all() {
  local item version
  for item in "${VERSIONS[@]}"; do
    version="${item%%:*}"
    place_one "$version"
  done
}

route_one() {
  local version="$1"
  ensure_version "$version"
  generate_one "$version"
  if [ ! -f "$(post_dp_def "$version")" ]; then
    echo "Missing legalized DEF for $version: $(post_dp_def "$version")" >&2
    echo "Run '$0 place $version' first." >&2
    exit 1
  fi
  ensure_absent "$(route_log "$version")"
  ensure_absent "$(route_guide "$version")"
  ensure_absent "$(congestion_report "$version")"
  ensure_absent "$(droute_drc_report "$version")"
  ensure_absent "$(check_drc_report "$version")"
  ensure_absent "$(drc_summary "$version")"
  ensure_absent "$(routed_def "$version")"
  mkdir -p "$(version_dir "$version")/routing" "$(version_dir "$version")/logs"
  "$OPENROAD_BIN" -no_init -no_splash -exit -log "$(route_log "$version")" "$(route_tcl "$version")"
  if [ ! -f "$(congestion_report "$version")" ]; then
    awk '
      /Final congestion report:/ {capture=1}
      capture {print}
      capture && /Total wirelength:/ {capture=0}
    ' "$(route_log "$version")" > "$(congestion_report "$version")"
  fi
  echo "Routed/evaluated $version"
  echo "  Route log: $(route_log "$version")"
  echo "  Congestion report: $(congestion_report "$version")"
  echo "  DRC summary: $(drc_summary "$version")"
  echo "  Routed DEF, if detailed_route succeeded: $(routed_def "$version")"
}

route_all() {
  local item version
  for item in "${VERSIONS[@]}"; do
    version="${item%%:*}"
    route_one "$version"
  done
}

open_gui() {
  local version="$1"
  ensure_version "$version"
  generate_one "$version"
  if [ ! -f "$(post_gp_def "$version")" ] && [ ! -f "$(post_dp_def "$version")" ]; then
    echo "No placed DEF found for $version. Run '$0 place $version' first." >&2
    exit 1
  fi
  "$OPENROAD_BIN" -gui "$(gui_tcl "$version")"
}

action="${1:-generate}"
case "$action" in
  generate)
    generate_all
    ;;
  place)
    if [ $# -ne 2 ]; then usage >&2; exit 1; fi
    place_one "$2"
    ;;
  place-all)
    place_all
    ;;
  route)
    if [ $# -ne 2 ]; then usage >&2; exit 1; fi
    route_one "$2"
    ;;
  route-all)
    route_all
    ;;
  gui)
    if [ $# -ne 2 ]; then usage >&2; exit 1; fi
    open_gui "$2"
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage >&2
    exit 1
    ;;
esac
