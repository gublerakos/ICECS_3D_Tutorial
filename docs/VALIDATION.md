# Validation record — 15 October 2026

## Packaged tutorial

- Shell syntax checks passed for all flow and smoke scripts.
- The SDC regression passed: exactly five Genus dont-use commands change; all
  other lines are preserved and the transformation is idempotent.
- `setup.py` verified the compressed input, original SDC, six PDK inputs, and
  unpacked CVA6 hash. It produced the ignored local reference netlist.
- `flow/run.sh check` passed on the packaged input/library paths and found
  48 compatible top masters.
- The packaged 1,000-cell smoke exercise passed partitioning, library generation,
  initial floorplanning, v2–v5 compact generation, v2 GP, v2 DP, and
  `check_placement -verbose`. A second smoke run verified the final library
  notices and atomic GP/DP DEF handoff.
- The smoke tests use the installed reference OpenROAD executable. They do not
  validate a freshly built or stock OpenROAD; see `tools/openroad/README.md`.
- Files selected for Git total approximately 54 MiB, with the largest file
  approximately 44 MiB (compressed CVA6). The 543 MiB unpacked netlist is ignored.
- No remote is configured; nothing has been pushed. No existing CVA6 run was
  modified by packaging.

## Existing full CVA6 reference

The original workspace successfully generated all four compact floorplans and
completed v2 global and detailed placement. The v2 DP DEF contains 2,493,045
components; its small placement summary and partition statistics are included
under `03_heterogeneous_3d/reference/`. The original DP log reports:

| Metric | Value |
| --- | --- |
| Original HPWL | 35,249,271.6 µm |
| Legalized HPWL | 38,072,517.3 µm |
| Total displacement | 2,524,191.7 µm |
| Average displacement | 1.0 µm |
| Maximum displacement | 170.3 µm |

These are observed virtual-placement results. Full CVA6 placement has not been
rerun from the packaged repository, and no routed/signoff result is claimed.
