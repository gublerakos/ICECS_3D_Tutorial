# Open-Source Physical Design Flows for Monolithic and Heterogeneous 3D ICs using OpenROAD

Companion material for the ICECS tutorial by George Rafael Goudroumanis,
Maria Pantazi-Kypraiou, and Alberto Garcia-Ortiz.

| Part | Topic | Presenter(s) | Material |
| --- | --- | --- | --- |
| 1 | Foundations of 3D ICs and OpenROAD | Maria and George | `01_foundations/` — reserved for slides |
| 2 | Monolithic 3D physical design | George | `02_monolithic_3d/` — reserved |
| 3 | Heterogeneous 3D physical design | Maria | [Guided CVA6 lab](03_heterogeneous_3d/README.md) |

The first two folders intentionally contain only Git placeholders. The
[proposal](docs/tutorial-proposal.pdf) supplies the broader teaching context;
its hands-on module is integrated into Part 3 in this repository.

Part 3 maps a synthesized CVA6 RISC-V core onto **Nangate 15 nm bottom** and
**Nangate 45 nm top** views. It teaches area-aware partitioning, LEF abstraction,
BOTTOM–TOP–BOTTOM floorplanning, global placement, detailed placement, and
experimental routing evaluation. Attendees need no commercial EDA license:
the starting netlist is supplied; its original synthesis used Cadence Genus.

## Start here

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

This package supports the heterogeneous **placement** methodology. Routing is
an optional virtual 2D experiment. It does not provide validated heterogeneous
CTS, PDN, timing closure, extraction, true 3D routing, or signoff. The proposal
covers the broader tutorial; it is not a claim that every stage is implemented
in Part 3. The reference full CVA6 v2 GP and DP completed successfully.

The scripts are portable copies of the local VGA/CVA6 flow, with all required
helpers included and no dependency on the original workstation paths. See
[provenance](docs/PROVENANCE.md), [validation](docs/VALIDATION.md), and
[third-party notices](THIRD_PARTY_NOTICES.md).

Tutorial code and documentation are provided under Apache-2.0; third-party
materials retain their own licenses and notices. The proposal retains its authors'
rights. See [LICENSE](LICENSE) and [licenses](licenses/).

This work is associated with COIN-3D, funded by the European Union's Horizon
Europe programme under grant agreement No. 101159667, as acknowledged in the proposal.
