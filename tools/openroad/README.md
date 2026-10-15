# OpenROAD reference build

Reference source commit: `b6c92cb46620e3918832b3b6bb6d7807c1e4afe3`.
Version string: `v2.0-25056-gb6c92cb466`.

The local source tree used alongside the validated executable contains the
attached modification to `src/dpl/src/infrastructure/Grid.cpp`: it disables the
DPL equal-site-width error and assigns the grid site width as rows are examined.
The tutorial uses different bottom and top sites. An unmodified build can reject
these with DPL-0051. The executable's version string alone does not identify
local changes; the local binary has not been independently rebuilt here.

For an explicit reference-build experiment, in a separate OpenROAD checkout:

```bash
git checkout b6c92cb46620e3918832b3b6bb6d7807c1e4afe3
git submodule update --init --recursive
git apply --check /path/to/ICECS_3D_Tutorial/tools/openroad/mixed-site-width-reference.patch
git apply /path/to/ICECS_3D_Tutorial/tools/openroad/mixed-site-width-reference.patch
```

Then follow the build instructions from that checkout, export `OPENROAD_BIN` to
the resulting executable, and run the tutorial's smoke test. The patch is
included for reproducibility of the existing research setup, not as a general
solution to mixed-width legalization. `check_placement` is explicitly called in
the packaged DP stage. Placement checking within this virtual representation
does not establish true 3D physical correctness.

This dependency is a discrepancy with the proposal's broad “no engine changes”
description. Resolve it before making that claim for this exact example: either
validate a stock-compatible abstraction or clearly disclose the reference patch.
No existing installation is modified by the tutorial scripts.

The upstream file is BSD-3-Clause; see `../../licenses/OpenROAD-BSD-3-Clause.txt`.
