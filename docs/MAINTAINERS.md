# Maintaining and publishing the tutorial

The local repository has no remote and has not been pushed. Parts 1 and 2 are
reserved; their `.gitkeep` files make the empty folders visible in Git. Add the
presentations later. The proposal remains in `docs/` as context.

The CVA6 input is gzip-compressed to about 44 MiB and is suitable for this initial
source distribution. Its uncompressed copy and all run products are ignored.
Avoid committing new DEFs, ODBs, logs, binaries, Genus checkpoints, or entire PDK
source trees. For future large dataset versions, use GitHub Release assets or
Git LFS rather than growing ordinary Git history.

Before publication, resolve the reference OpenROAD patch dependency documented
in `tools/openroad/README.md`, select the attendee build, and rerun the smoke
exercise on that build. A fresh-machine full CVA6 replay is desirable; the current
full-design reference came from the original workspace. Verify the tutorial
code license/author credit and retained third-party notices with the presenters.
No remote upload or GitHub account operation is performed by the setup scripts.

Typical local review commands from the repository root:

```bash
git status --short
python3 -m unittest discover -s 03_heterogeneous_3d/tests
bash 03_heterogeneous_3d/tests/smoke.sh
```

No presentation for Part 3 is authored here yet; its lab guide can supply the
structure for Maria and George's presentation work.
