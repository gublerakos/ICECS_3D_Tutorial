# Part 2 — Monolithic 3D with Rocket cores

Presenter: George Rafael Goudroumanis. The goal is to follow a complete OpenROAD
flow for a two-tier monolithic 3D design and compare it with a 2D baseline. The
content comes from the `3DPX` repository (`3DPX_testcase/`) and is organized like
`03_heterogeneous_3d` in `ICECS_3D_Tutorial`. The original notes are preserved in
[synthesis/README.org](synthesis/README.org) and [synthesis/wk_systems.org](synthesis/wk_systems.org).

## Before the session

Use Linux, Bash, `flock` (util-linux), Python 3.12 (the 3D scripts call `python3.12`;
`place_cores.py` needs its f-string syntax) and an OpenROAD build on `PATH`. A
display is not needed. Set `OPENROAD_BIN=/absolute/path/to/openroad` if it is
not on `PATH`. The shipped logs come from `OpenROAD v2.0-21011-gbb2a3e831`;
the first stage of the 3D flow and the start of the 2D flow were checked with
`v2.0-21429-gc0b3e0dc`, but a complete run of the new layout has not been done.
The Tcl scripts use 12 threads.

```bash
python3 setup.py                         # verifies checksums of data/ and pdk/
python3 -m unittest discover -s tests    # wiring checks, no OpenROAD needed
bash tests/smoke.sh                      # prepares all four run directories
./flow/run.sh check                      # inputs and OpenROAD executable
```

## Layout

| Directory | Purpose |
| --- | --- |
| `data/netlists/` | Genus netlists and SDCs used by the 3D flows (`DualRocket.v`, `QuadRocket.v`, tiered tile netlists, `*.sdc`). |
| `data/netlists_2d/` | `DualRocket.v` and `QuadRocket.v` read by the 2D baselines. |
| `data/manifest.json` | SHA-256 of every file in `data/` and `pdk/`, checked by `setup.py`. |
| `pdk/2D_Nangate45_PDK/`, `pdk/3D_Nangate45_PDK/` | 2D and tier-adapted (`_bottom_tier`/`_top_tier`, half-size, shrunk) technology, LEF, Liberty, RC and PDN views. |
| `pdk/fakeram/` | Fake SRAMs (`fakeram45_{64x32,1024x32,8192x64,16384x64}`) and their `*_3D` tier views. |
| `flow/` | `run.sh`, `config.sh`; `3d_dual/` and `3d_quad/` hold the `build_*.sh` drivers; `vars/` holds the per-step OpenROAD variable files. |
| `tcl_scripts/` | OpenROAD Tcl. `common/` is shared; `2d_*`, `3d_common/`, `3d_dual/`, `3d_quad/` are layered per variant. |
| `python_scripts/` | DEF/LEF helpers for the 3D flows (`3d_common/`, `3d_dual/`, `3d_quad/`). |
| `synthesis/` | How the netlists were made: `do_chipyard/` (Chipyard RTL), `do_genram/` (SRAM config), `do_synth/cmd/` (Genus scripts). Uses the original workstation paths; it is a record, not part of the attendee path. |
| `reference/` | Shipped results per variant: `outputs/`, `logs/`, `hier_rtlmp/`, `Post_placement.def`. |
| `tests/` | `test_layout.py` and `smoke.sh`. |

## Variants

`<mode>_<design>` with mode `2d`/`3d` and design `dual` (DualRocket) / `quad` (QuadRocket):
`2d_dual`, `2d_quad`, `3d_dual`, `3d_quad`. Each maps to one of the original directories
(`OpenRoad_2D_flow`, `OpenRoad_2D_flow_Quad_core`, `OpenRoad_3D_flow`, `OpenRoad_3D_flow_Quad_core`).
Files identical across variants live in the `common`/`*_common` folders; the
variant folder holds only what differs, for example the number of cores.

## Running a flow

```bash
./flow/run.sh list
./flow/run.sh prepare 3d_dual     # build runs/3d_dual/ only
./flow/run.sh run 3d_dual         # prepare, then run the whole flow
./flow/run.sh run 2d_dual
```

The scripts address files by relative paths (`./data`, `./tcl_scripts`,
`../do_synth`, `../do_genram`). `run.sh` therefore builds `runs/<variant>/work/`
with symbolic links to the layered sources, plus `runs/<variant>/do_synth` and
`do_genram` pointing at `pdk/` and `data/netlists/`. All products (`outputs/`,
logs, `hier_rtlmp/`) are written under `runs/`, which Git ignores; `build_3DIC.sh`
clears only that run's `outputs/` and logs, so `reference/` is never touched. Use an
absolute `RUN_DIR` for another location.

The 3D flow (`build_3DIC.sh`) calls `build_core*.sh` in the background and then builds
the full chip:

1. For each core: macro placement, then bottom-tier standard-cell placement;
   extract the full-chip DEF and concatenate the netlists.
2. Place the cores in the top level (`place_cores.py` / `place_core.py`) and the
   DigitalTop macros.
3. Place the top tier (covers added and removed by `add_covers.py` / `remove_covers.py`),
   then incrementally place the bottom tier for routability.
4. Create the PDN and CTS.
5. Legalize the top and bottom tiers, using the `format_def_*` helpers to fix and
   unfix the instances of each tier between steps.
6. Run `check_routing.tcl`.

The 2D baseline runs `tcl_scripts/<variant>/flow.tcl` with `Nangate45_2D_PDK.vars`.
Plan for substantial disk space (the reference results alone are about 7 GB) and RAM;
the 3D flows are long-running.

## The 3D representation

Each tier has its own cell and layer names: cells carry `_bottom_tier` / `_top_tier`
suffixes and layers are named `metalN_bottom_tier` / `metalN_top_tier` (see
`flow/vars/3d_common/Nangate45_3D_PDK.vars`). Half-size and shrunk LEF variants
support the floorplans of each tier.

## Reference results

`reference/<variant>/outputs/` holds the intermediate and final DEFs and Verilog (for
example `DigitalTop_post_place.def`, `DigitalTop_post_cts_all_legal.def`), and
`reference/<variant>/logs/` the matching OpenROAD logs. `reference/2d_*/Post_placement.def`
is the 2D placement. `Full_Chip_Placement_end` is a marker file from the original
repository, and `reference/3d_quad/outputs_copy/` is a stray copy of `data/` and
`hier_rtlmp/` kept as found.

## Suggested exercises

1. Compare the 2D and 3D placements of DualRocket: footprint, macro locations
   (`reference/3d_dual/outputs/Macros_locations.tcl`) and wirelength.
2. Read `flow/vars/3d_common/Nangate45_3D_PDK.vars` and explain how the tiers are
   separated by naming.
3. Follow one DEF through the `format_def_*` scripts and explain why instances are
   fixed or unfixed between steps.
4. Inspect `create_cts.log` and `check_routing.log` for the tier-specific results.

## Known issues carried over from the original data

- `flow/vars/3d_common/Nangate45_3D_PDK_cores_creation_top_tier.vars` references
  `nangate_stdcell_bottom_tie_shrinkedr.lef`, which does not exist. It is reached only
  by `build_bank.sh` (and `build_ScratchpadBank_top_tier.tcl`), which `build_3DIC.sh`
  does not call; `data/netlists/ScratchpadBank.v` is empty.
- `build_3DIC.sh` in `3d_dual/` and `3d_quad/` contains commented-out paths from the
  original workstation, and `synthesis/` scripts use absolute paths of that machine.
- Synthesis requires Cadence Genus; the netlists are supplied so no commercial license
  is needed for the OpenROAD flows. Regenerating RTL needs a Chipyard checkout.
