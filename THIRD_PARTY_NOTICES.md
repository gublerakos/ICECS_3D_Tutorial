# Third-party material and modifications

## Nangate 15 nm

Copyright (C) 2004–2014, Silvaco Inc. The local original release identifies
Apache-2.0 in `licenses/Nangate15-NOTICE.txt`. The complete Apache license is
included in `licenses/Apache-2.0.txt`. `nangate15_original.lib` is unmodified.
The bottom LEF is the existing tier-named adapted view used by the CVA6 flow.

## Nangate 45 nm / FreePDK45 views

Nangate copyright/trademark notices remain in the Liberty. The public OpenROAD
Nangate45 platform distributes an Apache-2.0 license:
https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts/blob/master/flow/platforms/nangate45/LICENSE

The bundled top Liberty and LEF use `_top_tier` cell names; the technology LEF
and tracks are the local combined-tier adaptations used by the VGA/CVA6 flow.
These are educational views, not foundry-qualified fabrication/signoff PDKs.
Their exact local source filenames and source/shipped hashes are recorded in
`03_heterogeneous_3d/pdk/provenance.json`. Existing notices are retained. The
original modification authors/dates are not reconstructed by this package.

## CVA6 and instantiated RTL dependencies

Upstream: https://github.com/openhwgroup/cva6
Source checkout commit: `81245a47fad8fe1a5d562d953ef2662e099def76`.

CVA6 is distributed under Solderpad Hardware License 0.51, with file-specific
and dependency licenses. Copies of the local source tree's LICENSE files are
preserved, including their relative paths, under `licenses/cva6/`. They cover
CVA6 and dependencies such as CVFPU and common cells; the synthesis netlist is a
mechanical transformation of the hardware, not newly authored RTL. The testcase
includes the selected RV64GC configuration and standard-cell-mapped caches.
The RTL source is not duplicated; use the upstream commit for source review.
See `docs/PROVENANCE.md` for the synthesis and library transformation history.

## OpenROAD

The tool itself is not bundled. The included reference source patch is derived
from BSD-3-Clause OpenROAD code. Its license is retained in
`licenses/OpenROAD-BSD-3-Clause.txt`. See `tools/openroad/README.md`.

## Tutorial material

The tutorial scripts derive from the local VGA and CVA6 methodology; packaged
changes include relative paths, a bundled Python partitioner, SDC translation,
input hashing, a smoke exercise, explicit stage messages, and DP checking.
The proposal PDF retains its authors' rights. Third-party licenses are not
replaced by the root Apache-2.0 license for tutorial code and documentation.
