#!/usr/bin/env bash
set -euo pipefail
PART="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/icecs-mono-smoke.XXXXXX")"
python3 "$PART/setup.py"
for variant in $("$PART/flow/run.sh" list); do
  RUN_DIR="$WORK/$variant" "$PART/flow/run.sh" prepare "$variant"
  test -d "$WORK/$variant/work/tcl_scripts"
  test -e "$WORK/$variant/do_synth/3D_Nangate45_PDK/nangate_tech.lef"
done
python3 -m unittest discover -s "$PART/tests"
echo "Smoke test passed. Run directories retained at $WORK"
