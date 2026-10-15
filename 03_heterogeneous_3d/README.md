# Part 3 — Heterogeneous 3D with CVA6

Presenter: Maria Pantazi-Kypraiou. The goal is to understand how two cell
technologies can share an OpenROAD placement abstraction and what that
abstraction does and does not represent.

## Before the session

Use Linux, Python 3.9 or newer, Bash, `flock` (util-linux), and an OpenROAD build
with Tcl/Python support as provided by its normal build. No Python packages are
required. A display is needed only for `gui`. Install OpenROAD following its
[official instructions](https://github.com/The-OpenROAD-Project/OpenROAD).
Read the [reference build notes](../tools/openroad/README.md): the local source
contains a patch disabling the mixed-site-width rejection; an unmodified build
is not validated. The local reference executable identifies as `v2.0-25056-gb6c92cb466`; other
versions should pass the smoke test before attempting CVA6. The binary is not
bundled. Set `OPENROAD_BIN=/absolute/path/to/openroad` if it is not on PATH.

Plan for at least 16 GB of free disk space and a workstation with substantial
RAM (64 GB recommended as planning headroom, not a measured minimum).
CVA6 has 2.49 million cells because cache memories were mapped to standard cells.
The reference DP process alone was observed using about 9.2 GiB; that is not a
peak-memory measurement for the whole flow. Prepare the full example before
class. Use the smoke test to check participant installations during the session.

From this directory:

```bash
python3 setup.py                  # verifies hashes; unpacks the supplied netlist
bash tests/smoke.sh               # 1,000-cell setup exercise, actual GP and DP
./flow/run.sh check               # required files and compatible library pairs
```

The smoke example is an inverter chain, not a reduced CVA6 benchmark. Its only
purpose is to exercise libraries, partitioning, SDC translation, floorplans,
and OpenROAD stage handoffs quickly.

## Guided lab

### 1. Inspect the starting point

Read `data/manifest.json` and `reference/tier_balance.json`. The CPU configuration
is `cv64a6_imafdc_sv39`. The supplied all-bottom mapped Verilog is the input;
there is no need to rebuild the RTL or run Genus. `data/cva6.sdc` preserves the
exported constraints. Inspect its `set_units` before interpreting clock numbers;
this tutorial does not claim timing closure or an achieved operating frequency.

**Question:** Why does balancing instance counts fail when the two technologies
have different cell areas?

### 2. Partition by native physical area

```bash
./flow/run.sh prepare
```

The partitioner compares compatible Liberty functions, logical pin directions,
and sequential behavior, then greedily balances native LEF areas. It renames
pins when compatible cells use different pin names. Unsupported pairs remain
bottom. In this library pair the flip-flops remain bottom. It rejects unknown
masters, missing physical views, an empty tier, and imbalance above 2%.

Inspect `runs/cva6_45nm_top_15nm_bottom/partition/partition.rpt` and
`tier_balance.json`. Expected counts are 513,073 top and 1,979,972 bottom cells,
with native area about 652,317 µm² per tier. This compatibility check is not
formal equivalence.

**Exercise:** Explain why top cells are fewer even though top and bottom areas
are nearly equal. Use `masters` in the JSON to identify which cells dominate.

### 3. Build the virtual floorplans

```bash
./flow/run.sh generate
```

OpenROAD first links the mixed netlist and reads the translated SDC. The helper
then replaces initial rows with repeated BOTTOM–TOP–BOTTOM groups, using row
orientations `N,N,FS,N,FS,FS` and a routing guard band at each edge.

```mermaid
flowchart LR
  A[All-bottom CVA6] --> B[Compatible area partition]
  B --> C[Initial floorplan]
  C --> D[Virtual BOTTOM–TOP–BOTTOM rows]
  D --> E[Global placement: top height 0.700 µm]
  E --> F[Detailed placement: top height 0.466 µm]
  F --> G[Optional virtual routing evaluation]
```

The native top height is 1.4 µm; its generated GP height is 0.700 µm and DP
height is 0.466 µm. Virtual site height is 0.466 µm. Native cell area used for
partitioning differs from the virtual area used in placement. The generator
retains connectivity while changing rows and DIEAREA.

| Version | Capacity multiplier | Interpretation |
| --- | --- | --- |
| v2 | 1.0 | Baseline compact floorplan |
| v3 | 1.2 | More row capacity |
| v4 | 1.3 | More row capacity |
| v5 | 1.5 | Most whitespace in this sweep |

**Exercise:** Compare the four `reports/heterogeneous_compact_v*.rpt` files.
Find required rows, generated rows, tier utilization, flat utilization, and
DIEAREA. Explain why equal native tier area does not imply equal virtual usage.

### 4. Place and inspect

```bash
./flow/run.sh place v2
./flow/run.sh gui v2
```

Two OpenROAD processes run in sequence: GP then DP. “Global placement finished”
is the first-stage completion message. DP reloads the design with its dedicated
top LEF and can be quiet for many minutes. Completion prints `Placed v2` and
writes `defs/postDP_compact_v2.def`. This packaged version also runs
`check_placement -verbose` before publishing that DEF.

The reference full run recorded original HPWL 35,249,271.6 µm and legalized
HPWL 38,072,517.3 µm, with average displacement 1.0 µm and maximum 170.3 µm.
These are virtual-placement metrics, not physical 3D routed wirelength.
See `reference/v2_placement.txt`. Different tool versions can give different results.

**Exercise:** Run `place v3`, then compare HPWL, legalization displacement,
utilization, and footprint. Does extra space help legalization at the cost of
wirelength? `place-all` runs all four and is intended for offline work.

### 5. Optional routing exploration

```bash
./flow/run.sh route v2
```

This follows the VGA experiment: top M1 pins are remapped to bottom M1 in a
route-only LEF, with bottom M1–M6 routing. It attempts global routing and then
detailed routing; detailed-routing failure is recorded in the DRC summary.
Inspect the summary, not just the shell exit code. Successful global routing
is not evidence of DRC-clean detailed routing or true 3D routability. The current
technology views have known via/pin warnings; this is an advanced experiment,
not a required successful end point for attendees.

## Outputs, reruns, and troubleshooting

`runs/cva6_45nm_top_15nm_bottom/` contains `inputs.json` with hashes/settings,
`partition/`, `initial/`, and one `outputs_cva6_util70_virtualrow_v*/` per variant.
All run products are ignored by Git. Source netlists and libraries are preserved.
Changing input contents/settings requires a new absolute `RUN_DIR`, for example:

```bash
RUN_DIR="$PWD/runs/alternative" GP_DENSITY=0.75 ./flow/run.sh generate
RUN_DIR="$PWD/runs/alternative" GP_DENSITY=0.75 ./flow/run.sh place v2
```

Keep the same overrides for later commands. A lock prevents concurrent use of
the same run. Existing successful placement outputs are not overwritten. A
completed GP DEF is reused when retrying `place v2` after a DP failure. A partial
partition requires a fresh run directory. Do not edit or move an active run.

- `STA-0565 set_dont_use`: generated SDC conversion removes Genus's explicit
  `true` argument. Run the packaged driver, not the original source SDC directly.
- Quiet DP: inspect the DP log and process CPU time. CPU activity does not prove
  convergence. Do not start a second run in the same directory.
- Missing `openroad`: put it on PATH or export `OPENROAD_BIN`.
- Missing netlist: run `python3 setup.py`.
- Library checksum mismatch: use a fresh checkout or document changes in a new
  experiment rather than mixing modified libraries with reference results.
- Insufficient memory: use the small smoke exercise and inspect reference
  summaries during class; do full CVA6 on a larger workstation.

## Suggested live sequence

Allow about 30 minutes: 5 for input/library inspection, 8 for partition and
virtual-row explanation, 10 for prepared placement results and GUI inspection,
and 7 for comparing capacity variants and discussing limitations. Run expensive
CVA6 stages before class; actual runtime is not constrained to this schedule.
