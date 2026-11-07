# Open-Source Physical Design Flows for Monolithic and Heterogeneous 3D ICs using OpenROAD

Companion material for the ICECS tutorial by George Rafael Goudroumanis,
Maria Pantazi-Kypraiou, and Alberto Garcia-Ortiz.

| Part | Topic | Presenter(s) | Material |
| --- | --- | --- | --- |
| 1 | Foundations of 3D ICs and OpenROAD | Maria and George | `01_foundations/` — reserved for slides |
| 2 | Monolithic 3D physical design | George | [Rocket-core two-tier lab](02_monolithic_3d/README.md) |
| 3 | Heterogeneous 3D physical design | Maria | [Guided CVA6 lab](03_heterogeneous_3d/README.md) |

The first folder intentionally contains only a Git placeholder. The
[proposal](docs/tutorial-proposal.pdf) supplies the broader teaching context;
its hands-on module is integrated into Part 3 in this repository.

Part 2 runs OpenROAD flows on Chipyard-generated **Rocket** systems
(`DualRocketConfig`, `QuadRocketConfig`) synthesized with Cadence Genus on Nangate
45 nm. It compares a conventional 2D baseline with a two-tier (bottom/top) 3D flow:
macro placement, per-core builds, full-chip placement, PDN, CTS, tier legalization
and a routability check. The Genus netlists, tier-adapted PDK views, fake SRAMs and
the complete reference results (DEFs and logs) are included.

Part 3 maps a synthesized CVA6 RISC-V core onto **Nangate 15 nm bottom** and
**Nangate 45 nm top** views. It teaches area-aware partitioning, LEF abstraction,
BOTTOM–TOP–BOTTOM floorplanning, global placement, detailed placement, and
experimental routing evaluation. Attendees need no commercial EDA license:
the starting netlist is supplied; its original synthesis used Cadence Genus.

## Start here

### Part 2 — monolithic 3D

The Verilog netlists and DEF files of Part 2 (`02_monolithic_3d/**/*.v` and
`**/*.def`, see [.gitattributes](.gitattributes)) are stored with
[Git LFS](https://git-lfs.com). Install Git LFS **before** cloning, otherwise these
files appear as small text pointers (`version https://git-lfs.github.com/spec/v1`)
and `setup.py` reports checksum mismatches:

```bash
git lfs install                       # once per machine (Fedora/RHEL: sudo dnf install git-lfs)
git clone git@github.com:gublerakos/ICECS_3D_Tutorial.git
cd ICECS_3D_Tutorial
```

If you already cloned without LFS, fetch the real files in place:

```bash
git lfs install
git lfs pull
```

To download only what the flows need and skip the large reference results
(roughly 7 GB), exclude them:

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone git@github.com:gublerakos/ICECS_3D_Tutorial.git
cd ICECS_3D_Tutorial
git lfs pull --include="02_monolithic_3d/data,02_monolithic_3d/pdk,02_monolithic_3d/synthesis"
# later, if wanted:
git lfs pull --include="02_monolithic_3d/reference/3d_dual"
```

Check with `git lfs ls-files` (a `*` after the hash marks a downloaded file; `-` marks
one that is still a pointer). To clone this branch directly, add
`-b Monolithic_cases`. `python3 02_monolithic_3d/setup.py` lists any files that are
missing or still pointers.

Read the [Part 2 guide](02_monolithic_3d/README.md). On Linux with Python 3.12, Bash,
`flock`, and OpenROAD on `PATH` (or `OPENROAD_BIN` set):

```bash
cd 02_monolithic_3d
python3 setup.py
bash tests/smoke.sh
./flow/run.sh list                 # 2d_dual 2d_quad 3d_dual 3d_quad
./flow/run.sh run 3d_dual
```

Flows run in `02_monolithic_3d/runs/<variant>/`, never in the shipped
`reference/` results. Part 2 has no OpenROAD source patch; the shipped logs come from
`v2.0-21011-gbb2a3e831`. The complete flows are long-running and need substantial
disk space and RAM (the reference results alone are about 7 GB, which makes the
Part 2 folder about 8 GB in total).

### Part 3 — heterogeneous 3D

First read the [reference OpenROAD build notes](tools/openroad/README.md): the
validated local setup has a mixed-site-width source patch. Stock OpenROAD has
not been validated. On Linux with Python 3.9+, Bash, `flock`, and the selected
OpenROAD executable available on `PATH`:

```bash
cd 03_heterogeneous_3d
python3 setup.py
bash tests/smoke.sh
./flow/run.sh check
./flow/run.sh generate
./flow/run.sh place v2
./flow/run.sh gui v2
```

The smoke test is small; the full CVA6 exercise has 2,493,045 cells and can take
much longer than a live tutorial slot. Read the [lab guide](03_heterogeneous_3d/README.md)
for hardware planning, stages, exercises, and expected results. Large intermediate
results stay outside Git. The compressed input and required library views are
included, so no separate download is needed after obtaining this repository.

## Scope and reproducibility

Part 3 supports the heterogeneous **placement** methodology. Routing is
an optional virtual 2D experiment. It does not provide validated heterogeneous
CTS, PDN, timing closure, extraction, true 3D routing, or signoff. The proposal
covers the broader tutorial; it is not a claim that every stage is implemented
in Part 3. The reference full CVA6 v2 GP and DP completed successfully.

Part 2 ships research results from the original workspace. Its inputs are
checksum-verified by `setup.py` and its script wiring is tested, but no complete
flow has been re-run in this layout, and no signoff timing, extraction, true 3D
routing or DRC-clean claim is made. The Part 2 guide lists known issues carried
over from the original data.

The scripts are portable copies of the local VGA/CVA6 flow, with all required
helpers included and no dependency on the original workstation paths. See
[provenance](docs/PROVENANCE.md), [validation](docs/VALIDATION.md), and
[third-party notices](THIRD_PARTY_NOTICES.md).

Tutorial code and documentation are provided under Apache-2.0; third-party
materials retain their own licenses and notices. The proposal retains its authors'
rights. See [LICENSE](LICENSE) and [licenses](licenses/).

This work is associated with COIN-3D, funded by the European Union's Horizon
Europe programme under grant agreement No. 101159667, as acknowledged in the proposal.
