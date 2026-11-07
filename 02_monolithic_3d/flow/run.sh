#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/config.sh"
export OPENROAD_BIN="${OPENROAD_BIN:-openroad}"

usage() {
  echo "Usage: $0 list|check|prepare VARIANT|run VARIANT"
  echo "Variants: $VARIANTS  (<2d|3d>_<dual|quad>)"
  echo "Set RUN_DIR (absolute) to change the run location; default: $ROOT/runs/VARIANT."
  echo "Set OPENROAD_BIN to the OpenROAD executable if it is not on PATH."
}

valid_variant() {
  local v
  for v in $VARIANTS; do [[ "$v" = "$1" ]] && return 0; done
  return 1
}

# Link every file of tcl_scripts/, python_scripts/ or flow/vars/ layers into DEST.
# Later layers (the variant) override earlier ones (common files).
link_layers() {
  local dest="$1" kind="$2" layer file
  mkdir -p "$dest"
  for layer in common "${MODE}_common" "$VARIANT"; do
    [[ -d "$ROOT/$kind/$layer" ]] || continue
    for file in "$ROOT/$kind/$layer"/*; do
      ln -sfn "$file" "$dest/$(basename "$file")"
    done
  done
}

# The Tcl, Python and shell scripts use paths relative to the working
# directory (./data, ./tcl_scripts, ../do_synth, ../do_genram). Reproduce that
# layout in the run directory with symbolic links so the shipped sources are
# never modified and run products stay outside the source tree.
prepare() {
  VARIANT="$1"
  MODE="${VARIANT%%_*}"
  RUN_DIR="${RUN_DIR:-$ROOT/runs/$VARIANT}"
  [[ "$RUN_DIR" = /* ]] || { echo 'RUN_DIR must be absolute' >&2; exit 2; }
  WORK="$RUN_DIR/work"
  mkdir -p "$WORK" "$RUN_DIR/do_synth" "$RUN_DIR/do_genram" "$RUN_DIR/bin"
  ln -sfn "$ROOT/pdk/2D_Nangate45_PDK" "$RUN_DIR/do_synth/2D_Nangate45_PDK"
  ln -sfn "$ROOT/pdk/3D_Nangate45_PDK" "$RUN_DIR/do_synth/3D_Nangate45_PDK"
  ln -sfn "$ROOT/data/netlists" "$RUN_DIR/do_synth/results"
  ln -sfn "$ROOT/pdk/fakeram" "$RUN_DIR/do_genram/results"
  link_layers "$WORK/data" flow/vars
  link_layers "$WORK/tcl_scripts" tcl_scripts
  if [[ "$MODE" = 2d ]]; then
    local design="${VARIANT#*_}"
    design="$(tr '[:lower:]' '[:upper:]' <<< "${design:0:1}")${design:1}Rocket"
    ln -sfn "$ROOT/data/netlists_2d/$design.v" "$WORK/data/$design.v"
  else
    link_layers "$WORK/python_scripts" python_scripts
    mkdir -p "$WORK/outputs"
    for file in "$ROOT/flow/$VARIANT"/build_*.sh; do
      ln -sfn "$file" "$WORK/$(basename "$file")"
    done
  fi
  # The 3D scripts call python3.12 explicitly.
  if ! command -v python3.12 >/dev/null 2>&1; then
    ln -sfn "$(command -v python3)" "$RUN_DIR/bin/python3.12"
  fi
  export PATH="$RUN_DIR/bin:$PATH"
  if [[ "$OPENROAD_BIN" = */* ]]; then export PATH="$(dirname "$OPENROAD_BIN"):$PATH"; fi
  echo "Prepared $WORK"
}

action="${1:-}"
case "$action" in
  -h|--help|help|"") usage; exit 0 ;;
  list) echo "$VARIANTS"; exit 0 ;;
  check) [[ $# -eq 1 ]] || { usage; exit 2; } ;;
  prepare|run) [[ $# -eq 2 ]] && valid_variant "$2" || { usage; exit 2; } ;;
  *) usage; exit 2 ;;
esac

if [[ "$action" = check ]]; then
  python3 "$ROOT/setup.py"
  command -v "$OPENROAD_BIN" >/dev/null 2>&1 || { echo "Missing OpenROAD executable: $OPENROAD_BIN" >&2; exit 1; }
  echo "OpenROAD found: $(command -v "$OPENROAD_BIN")"
  exit 0
fi

prepare "$2"
[[ "$action" = run ]] || exit 0

exec 9>"$RUN_DIR/run.lock"
flock -n 9 || { echo "Another command is using $RUN_DIR" >&2; exit 1; }
command -v openroad >/dev/null 2>&1 || { echo "Missing OpenROAD executable: $OPENROAD_BIN" >&2; exit 1; }
cd "$WORK"
if [[ "$MODE" = 3d ]]; then
  # build_3DIC.sh clears outputs/ and *.log in this run directory first.
  exec bash build_3DIC.sh
else
  exec openroad -exit tcl_scripts/flow.tcl
fi
