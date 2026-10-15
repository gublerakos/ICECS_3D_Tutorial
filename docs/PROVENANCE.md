# Provenance and scope

The testcase is the all-bottom `cva6_bottom_reference.v` from synthesis run
`cva6_45nm_top_15nm_bottom_20261013_104817_utc`. Its header records Genus
23.13-s073_1; the CPU source checkout reports commit
`81245a47fad8fe1a5d562d953ef2662e099def76`. A checkout hash does not imply the
entire local source tree was clean. The compressed file is a deterministic gzip
copy of the actual reference, and SHA-256 hashes in `data/manifest.json` identify
the shipped artifact precisely. The SDC is supplied unchanged; only the generated
run copy translates five Genus `set_dont_use true` commands for OpenROAD.

The original synthesis selected `cv64a6_imafdc_sv39`, used native Nangate15
mapping, and synthesized the caches to standard cells. The synthesis flow made
generated copies of SRAM wrappers to retain their `tc_sram` implementations.
The attendee path starts after synthesis and does not require or reproduce Genus
RTL synthesis. This is an open-source physical-design tutorial, not a claim of
an entirely open-source RTL-to-netlist provenance.

The partition algorithm and compatibility parser come from
`Tutorial_ICECS/synthesis`; the exported Python module includes only the code
needed for library checks and partitioning. GP/DP wrappers come from the CVA6
flow, which adapted the VGA v5 compact capacity sweep. The three LEF/floorplan
helpers are included locally. Native area is used to partition, while virtual
area drives OpenROAD placement.

The libraries in `pdk/` are the actual 15/45 views used by that flow. The JSON
manifest records original workspace-relative paths for attribution only; no
script needs that workspace. Added modification notices identify tier-adapted
views. The clean bottom Liberty is regenerated from the original 15 nm release
in each run, avoiding the old duplicated-cell VGA Liberty.

The reference OpenROAD source checkout contains a mixed-site-width modification.
See `../tools/openroad/README.md` before choosing an OpenROAD build. A stock
build has not been validated. No CTS, PDN, true 3D extraction, timing closure,
or DRC-clean routed CVA6 result is included.
