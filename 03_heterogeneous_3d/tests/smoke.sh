#!/usr/bin/env bash
set -euo pipefail
PART="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/icecs-smoke.XXXXXX")"
python3 - "$WORK" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s='module cva6(clk_i, out);\ninput clk_i;\noutput out;\nwire [1000:0] n;\nassign n[0] = clk_i;\n'
s+=''.join(f'INV_X1_bottom_tier u{i} (.I(n[{i}]), .ZN(n[{i+1}]));\n' for i in range(1000))
s+='assign out = n[1000];\nendmodule\n'
(p/'reference.v').write_text(s)
(p/'test.sdc').write_text('create_clock -name core_clk -period 10 [get_ports clk_i]\nset_dont_use true [get_lib_cells */TIEL_bottom_tier]\n')
PY
export REFERENCE_NETLIST="$WORK/reference.v" SDC_FILE="$WORK/test.sdc" RUN_DIR="$WORK/run"
bash "$PART/flow/run.sh" generate
bash "$PART/flow/run.sh" place v2
test -s "$RUN_DIR/outputs_cva6_util70_virtualrow_v2/defs/postDP_compact_v2.def"
echo "Smoke test passed. Artifacts retained at $WORK"
