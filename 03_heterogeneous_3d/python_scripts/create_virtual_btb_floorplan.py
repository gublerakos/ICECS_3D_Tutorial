#!/usr/bin/env python3
"""Create a compact BOTTOM/TOP/BOTTOM virtual heterogeneous DEF.

The input DEF is never modified. The output DEF preserves non-row content and
changes only DIEAREA plus ROW statements. Row counts are area-estimated per
tier, then balanced with:

    N = max(required_top_rows, ceil(required_bottom_rows / 2))

The emitted pattern is exactly BOTTOM, TOP, BOTTOM repeated N times.

For OpenROAD, the virtual rows still live in one flat 2D DIEAREA. The row
count therefore also honors a flat-utilization constraint so OpenROAD does not
see total movable area greater than the compact virtual floorplan area.
"""

import argparse
import math
import os
import re
import sys
from collections import defaultdict


DEFAULT_BOTTOM_SITE = "NanGate_15nm_OCL"
DEFAULT_TOP_SITE = "FreePDK45_38x28_10R_NP_162NW_34O"
DEFAULT_ORIENTATION_PATTERN = "N,N,FS,N,FS,FS"


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-def", required=True, help="Original OpenROAD DEF")
    parser.add_argument("--output-def", required=True, help="New DEF to create")
    parser.add_argument(
        "--lef",
        action="append",
        required=True,
        help="LEF containing macro SIZE/SITE data. Pass once per LEF file.",
    )
    parser.add_argument("--bottom-site", default=DEFAULT_BOTTOM_SITE)
    parser.add_argument("--top-site", default=DEFAULT_TOP_SITE)
    parser.add_argument(
        "--utilization",
        type=float,
        default=0.80,
        help="Target utilization for estimating tier row demand. Default: 0.80",
    )
    parser.add_argument(
        "--flat-utilization",
        type=float,
        default=None,
        help=(
            "Target flat OpenROAD utilization for total movable area over the "
            "virtual DIEAREA. Default: same as --utilization."
        ),
    )
    parser.add_argument(
        "--capacity-basis",
        choices=["virtual", "split"],
        default="virtual",
        help=(
            "For B/T/B mode, choose how base N is sized. 'virtual' keeps the "
            "legacy OpenROAD flat-utilization guard: max(tier_required_n, "
            "flat_required_n, min_n). 'split' targets recovered tier utilization "
            "only: max(tier_required_n, min_n). Default: virtual."
        ),
    )
    parser.add_argument(
        "--min-n",
        type=int,
        default=1,
        help="Minimum B/T/B groups to emit when there are any tier cells. Default: 1",
    )
    parser.add_argument(
        "--capacity-scale",
        type=float,
        default=1.0,
        help="Scale base N before row generation, e.g. 1.2 for 20%% extra capacity.",
    )
    parser.add_argument(
        "--row-mode",
        choices=["btb", "demand"],
        default="btb",
        help=(
            "Row generation mode. 'btb' preserves BOTTOM/TOP/BOTTOM groups. "
            "'demand' emits only the required top and bottom rows, interleaved by demand. "
            "Default: btb"
        ),
    )
    parser.add_argument(
        "--vertical-spacing",
        choices=["pitch", "site-height"],
        default="pitch",
        help=(
            "Use the original row pitch for virtual rows, or advance y by each row site's "
            "actual height. Default: pitch"
        ),
    )
    parser.add_argument(
        "--orientation-pattern",
        default=DEFAULT_ORIENTATION_PATTERN,
        help=(
            "Comma-separated row orientation cycle. Default matches the original "
            "heterogeneous DEF: N,N,FS,N,FS,FS"
        ),
    )
    parser.add_argument(
        "--routing-guard-band-rows",
        type=float,
        default=0.0,
        help=(
            "Add this many virtual row pitches as empty DIEAREA guard band below "
            "the first generated row and above the last generated row. This helps "
            "routing when centered LEF origins make pins/blockages extend outside "
            "boundary rows. Default: 0."
        ),
    )
    parser.add_argument(
        "--report-file",
        help="Optional report file with row counts, utilization, and DIEAREA.",
    )
    parser.add_argument(
        "--version-label",
        default="",
        help="Optional label written into the report, e.g. v3.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite output DEF if it already exists. The input DEF is still protected.",
    )
    return parser.parse_args()


def read_lines(path):
    with open(path) as f:
        return f.readlines()


def parse_units(def_lines):
    for line in def_lines:
        match = re.search(r"\bUNITS\s+DISTANCE\s+MICRONS\s+(\d+)\s*;", line)
        if match:
            return int(match.group(1))
    raise SystemExit("Could not find DEF UNITS DISTANCE MICRONS")


def parse_diearea(def_lines):
    pattern = re.compile(
        r"DIEAREA\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)"
    )
    for line in def_lines:
        match = pattern.search(line)
        if match:
            return tuple(int(match.group(i)) for i in range(1, 5))
    raise SystemExit("Could not find DEF DIEAREA")


def parse_rows(def_lines):
    pattern = re.compile(
        r"^\s*ROW\s+(\S+)\s+(\S+)\s+(-?\d+)\s+(-?\d+)\s+(\S+)\s+DO\s+(\d+)\s+BY\s+(\d+)\s+STEP\s+(-?\d+)\s+(-?\d+)\s*;"
    )
    rows = []
    for line in def_lines:
        match = pattern.match(line)
        if not match:
            continue
        rows.append(
            {
                "name": match.group(1),
                "site": match.group(2),
                "x": int(match.group(3)),
                "y": int(match.group(4)),
                "orient": match.group(5),
                "do": int(match.group(6)),
                "by": int(match.group(7)),
                "step_x": int(match.group(8)),
                "step_y": int(match.group(9)),
            }
        )
    if not rows:
        raise SystemExit("No ROW statements found in input DEF")
    return rows


def choose_template(rows, site):
    for row in rows:
        if row["site"] == site:
            return row
    raise SystemExit("No ROW template found for site: %s" % site)


def infer_virtual_row_pitch(rows):
    ys_by_site = defaultdict(list)
    for row in rows:
        ys_by_site[row["site"]].append(row["y"])

    pitches = []
    for ys in ys_by_site.values():
        unique = sorted(set(ys))
        for prev, cur in zip(unique, unique[1:]):
            diff = cur - prev
            if diff > 0:
                pitches.append(diff)

    if pitches:
        return min(pitches)
    if rows[0]["step_y"] > 0:
        return rows[0]["step_y"]
    raise SystemExit("Could not infer virtual row pitch")


def parse_lef(lef_paths, dbu_per_micron):
    macros = {}
    sites = {}
    current_macro = None
    current_site = None

    macro_re = re.compile(r"^\s*MACRO\s+(\S+)")
    site_block_re = re.compile(r"^\s*SITE\s+(\S+)")
    end_re = re.compile(r"^\s*END\s+(\S+)")
    size_re = re.compile(r"\bSIZE\s+([0-9.]+)\s+BY\s+([0-9.]+)\s*;")
    macro_site_re = re.compile(r"\bSITE\s+(\S+)\s*;")

    for lef_path in lef_paths:
        with open(lef_path) as f:
            for line in f:
                macro_match = macro_re.match(line)
                if macro_match:
                    current_macro = {
                        "name": macro_match.group(1),
                        "width": None,
                        "height": None,
                        "site": None,
                    }
                    current_site = None
                    continue

                if current_macro is None:
                    site_match = site_block_re.match(line)
                    if site_match:
                        current_site = {"name": site_match.group(1), "width": None, "height": None}
                        continue

                size_match = size_re.search(line)
                if size_match:
                    width = int(round(float(size_match.group(1)) * dbu_per_micron))
                    height = int(round(float(size_match.group(2)) * dbu_per_micron))
                    if current_macro is not None:
                        current_macro["width"] = width
                        current_macro["height"] = height
                    elif current_site is not None:
                        current_site["width"] = width
                        current_site["height"] = height
                    continue

                if current_macro is not None:
                    macro_site_match = macro_site_re.search(line)
                    if macro_site_match:
                        current_macro["site"] = macro_site_match.group(1)
                        continue

                end_match = end_re.match(line)
                if not end_match:
                    continue

                end_name = end_match.group(1)
                if current_macro is not None and end_name == current_macro["name"]:
                    if current_macro["width"] is not None and current_macro["height"] is not None:
                        macros[current_macro["name"]] = current_macro
                    current_macro = None
                elif current_site is not None and end_name == current_site["name"]:
                    if current_site["height"] is not None:
                        sites[current_site["name"]] = current_site
                    current_site = None

    return macros, sites


def parse_components(def_lines):
    components = []
    in_components = False
    comp_re = re.compile(r"^\s*-\s+(\S+)\s+(\S+)")
    for line in def_lines:
        stripped = line.strip()
        if stripped.startswith("COMPONENTS "):
            in_components = True
            continue
        if in_components and stripped == "END COMPONENTS":
            break
        if not in_components:
            continue
        match = comp_re.match(line)
        if match:
            components.append((match.group(1), match.group(2)))
    if not components:
        raise SystemExit("No COMPONENTS found in input DEF")
    return components


def classify_tier(master, macro, bottom_site, top_site):
    site = macro.get("site") if macro else None
    if site == bottom_site or "_bottom_tier" in master:
        return "BOTTOM"
    if site == top_site or "_top_tier" in master:
        return "TOP"
    return None


def compute_tier_areas(components, macros, bottom_site, top_site):
    areas = {"BOTTOM": 0, "TOP": 0}
    counts = {"BOTTOM": 0, "TOP": 0}
    missing_macros = defaultdict(int)
    unknown_tier = defaultdict(int)

    for _inst, master in components:
        macro = macros.get(master)
        tier = classify_tier(master, macro, bottom_site, top_site)
        if tier is None:
            unknown_tier[master] += 1
            continue
        if macro is None:
            missing_macros[master] += 1
            continue
        areas[tier] += macro["width"] * macro["height"]
        counts[tier] += 1

    return areas, counts, missing_macros, unknown_tier


def fallback_site_height(site, macros, row_pitch):
    heights = [macro["height"] for macro in macros.values() if macro.get("site") == site]
    if heights:
        return max(set(heights), key=heights.count)
    return row_pitch


def site_height(site, sites, macros, row_pitch):
    if site in sites and sites[site].get("height"):
        return sites[site]["height"]
    return fallback_site_height(site, macros, row_pitch)


def macro_capacity_height(site, macros, row_pitch):
    return fallback_site_height(site, macros, row_pitch)


def required_rows(area, row_width, row_height, utilization):
    if area <= 0:
        return 0
    return int(math.ceil(float(area) / (float(row_width) * float(row_height) * utilization)))


def required_flat_height_and_rows(area, row_width, row_pitch, utilization):
    if area <= 0:
        return 0, 0
    required_height = int(math.ceil(float(area) / (float(row_width) * utilization)))
    required_row_slots = int(math.ceil(float(required_height) / float(row_pitch)))
    return required_height, required_row_slots


def parse_orientation_pattern(pattern):
    orientations = [item.strip() for item in pattern.split(",") if item.strip()]
    if not orientations:
        raise SystemExit("--orientation-pattern must contain at least one orientation")
    allowed = set(["N", "S", "E", "W", "FN", "FS", "FE", "FW"])
    invalid = [orient for orient in orientations if orient not in allowed]
    if invalid:
        raise SystemExit(
            "Invalid orientation(s) in --orientation-pattern: %s" % ", ".join(invalid)
        )
    return orientations


def orientation(index, orientation_pattern):
    return orientation_pattern[index % len(orientation_pattern)]


def make_row_line(row_idx, template, y, orientation_pattern):
    return (
        "ROW VROW_%d %s %d %d %s DO %d BY %d STEP %d %d ;\n"
        % (
            row_idx,
            template["site"],
            template["x"],
            y,
            orientation(row_idx, orientation_pattern),
            template["do"],
            template["by"],
            template["step_x"],
            template["step_y"],
        )
    )


def make_rows_from_sequence(sequence, bottom_template, top_template, row_pitch, row_heights,
                            vertical_spacing, orientation_pattern, y_start=0):
    rows = []
    y = y_start
    for row_idx, tier in enumerate(sequence):
        template = top_template if tier == "TOP" else bottom_template
        rows.append(make_row_line(row_idx, template, y, orientation_pattern))
        if vertical_spacing == "site-height":
            y += row_heights[tier]
        else:
            y += row_pitch
    return rows, y - y_start


def make_btb_rows(n_groups, bottom_template, top_template, row_pitch, row_heights,
                  vertical_spacing, orientation_pattern, y_start=0):
    sequence = []
    for _group in range(n_groups):
        sequence.extend(["BOTTOM", "TOP", "BOTTOM"])
    return make_rows_from_sequence(
        sequence,
        bottom_template,
        top_template,
        row_pitch,
        row_heights,
        vertical_spacing,
        orientation_pattern,
        y_start,
    )


def make_demand_sequence(bottom_rows, top_rows):
    total = bottom_rows + top_rows
    if total <= 0:
        return []

    sequence = []
    emitted = {"BOTTOM": 0, "TOP": 0}

    # Prefer a bottom row at y=0 when possible to keep the virtual floorplan
    # close to the original convention, then distribute the remaining rows.
    if bottom_rows > 0:
        sequence.append("BOTTOM")
        emitted["BOTTOM"] = 1

    while len(sequence) < total:
        slot = len(sequence) + 1
        ideal_top = int(round(float(slot) * float(top_rows) / float(total)))
        if emitted["TOP"] < top_rows and emitted["TOP"] < ideal_top:
            sequence.append("TOP")
            emitted["TOP"] += 1
        elif emitted["BOTTOM"] < bottom_rows:
            sequence.append("BOTTOM")
            emitted["BOTTOM"] += 1
        else:
            sequence.append("TOP")
            emitted["TOP"] += 1

    return sequence


def make_demand_rows(bottom_rows, top_rows, bottom_template, top_template, row_pitch,
                     row_heights, vertical_spacing, orientation_pattern, y_start=0):
    sequence = make_demand_sequence(bottom_rows, top_rows)
    return make_rows_from_sequence(
        sequence,
        bottom_template,
        top_template,
        row_pitch,
        row_heights,
        vertical_spacing,
        orientation_pattern,
        y_start,
    )


def replace_diearea(line, diearea):
    x_min, y_min, x_max, y_max = diearea
    return re.sub(
        r"DIEAREA\s*\(\s*-?\d+\s+-?\d+\s*\)\s*\(\s*-?\d+\s+-?\d+\s*\)\s*;",
        "DIEAREA ( %d %d ) ( %d %d ) ;" % (x_min, y_min, x_max, y_max),
        line,
    )


def write_def(def_lines, output_def, new_rows, new_diearea):
    inserted_rows = False
    with open(output_def, "w") as out:
        for line in def_lines:
            if line.lstrip().startswith("ROW "):
                if not inserted_rows:
                    for row in new_rows:
                        out.write(row)
                    inserted_rows = True
                continue
            if line.lstrip().startswith("DIEAREA "):
                out.write(replace_diearea(line, new_diearea))
            else:
                out.write(line)
    if not inserted_rows:
        raise SystemExit("No original ROW block found for row replacement")


def utilization(area, rows, row_width, row_height):
    if rows <= 0:
        return 0.0
    return float(area) / float(rows * row_width * row_height)


def write_report(report_file, report):
    report_dir = os.path.dirname(os.path.abspath(report_file))
    if report_dir and not os.path.isdir(report_dir):
        os.makedirs(report_dir)
    with open(report_file, "w") as f:
        for key in [
            "version_label",
            "row_mode",
            "vertical_spacing",
            "orientation_pattern",
            "capacity_basis",
            "input_def",
            "output_def",
            "required_top_rows",
            "required_bottom_rows",
            "tier_required_n",
            "flat_required_height_dbu",
            "flat_required_row_slots",
            "flat_required_n",
            "base_n",
            "version_scaling_factor",
            "final_n_version",
            "generated_top_rows",
            "generated_bottom_rows",
            "total_generated_rows",
            "final_diearea",
            "routing_guard_band_rows",
            "routing_guard_band_dbu",
            "estimated_top_utilization",
            "estimated_bottom_utilization",
            "top_cell_count",
            "bottom_cell_count",
            "top_cell_area_dbu2",
            "bottom_cell_area_dbu2",
            "total_cell_area_dbu2",
            "row_width_dbu",
            "top_row_height_dbu",
            "bottom_row_height_dbu",
            "top_site_height_dbu",
            "bottom_site_height_dbu",
            "top_macro_height_dbu",
            "bottom_macro_height_dbu",
            "virtual_row_pitch_dbu",
            "target_utilization_for_required_rows",
            "target_flat_utilization",
            "estimated_flat_utilization",
        ]:
            f.write("%s: %s\n" % (key, report[key]))


def main():
    args = parse_args()
    input_def = os.path.abspath(args.input_def)
    output_def = os.path.abspath(args.output_def)
    report_file = os.path.abspath(args.report_file) if args.report_file else None

    if input_def == output_def:
        raise SystemExit("Refusing to overwrite input DEF")
    if os.path.exists(output_def) and not args.force:
        raise SystemExit("Output already exists; refusing to overwrite: %s" % output_def)
    if report_file and os.path.exists(report_file) and not args.force:
        raise SystemExit("Report already exists; refusing to overwrite: %s" % report_file)
    if args.utilization <= 0.0 or args.utilization > 1.0:
        raise SystemExit("--utilization must be in the range (0, 1]")
    flat_utilization = args.flat_utilization
    if flat_utilization is None:
        flat_utilization = args.utilization
    if flat_utilization <= 0.0 or flat_utilization > 1.0:
        raise SystemExit("--flat-utilization must be in the range (0, 1]")
    if args.capacity_scale < 1.0:
        raise SystemExit("--capacity-scale must be >= 1.0")
    if args.routing_guard_band_rows < 0.0:
        raise SystemExit("--routing-guard-band-rows must be >= 0")

    def_lines = read_lines(input_def)
    dbu = parse_units(def_lines)
    x_min, y_min, x_max, _old_y_max = parse_diearea(def_lines)
    rows = parse_rows(def_lines)
    bottom_template = choose_template(rows, args.bottom_site)
    top_template = choose_template(rows, args.top_site)
    row_pitch = infer_virtual_row_pitch(rows)
    routing_guard_band_dbu = int(math.ceil(args.routing_guard_band_rows * row_pitch))
    row_y_start = y_min + routing_guard_band_dbu
    orientation_pattern = parse_orientation_pattern(args.orientation_pattern)

    macros, sites = parse_lef(args.lef, dbu)
    components = parse_components(def_lines)
    areas, counts, missing, unknown = compute_tier_areas(
        components, macros, args.bottom_site, args.top_site
    )

    bottom_site_height = site_height(args.bottom_site, sites, macros, row_pitch)
    top_site_height = site_height(args.top_site, sites, macros, row_pitch)
    bottom_macro_height = macro_capacity_height(args.bottom_site, macros, row_pitch)
    top_macro_height = macro_capacity_height(args.top_site, macros, row_pitch)
    row_width = min(
        x_max - x_min,
        bottom_template["do"] * bottom_template["step_x"],
        top_template["do"] * top_template["step_x"],
    )

    required_bottom = required_rows(
        areas["BOTTOM"], row_width, bottom_macro_height, args.utilization
    )
    required_top = required_rows(areas["TOP"], row_width, top_macro_height, args.utilization)
    total_area = areas["BOTTOM"] + areas["TOP"]
    flat_required_height, flat_required_row_slots = required_flat_height_and_rows(
        total_area, row_width, row_pitch, flat_utilization
    )
    flat_required_n = int(math.ceil(flat_required_row_slots / 3.0))

    row_heights = {
        "BOTTOM": bottom_site_height,
        "TOP": top_site_height,
    }
    tier_required_n = 0

    if counts["BOTTOM"] or counts["TOP"]:
        if args.row_mode == "btb":
            tier_required_n = max(required_top, int(math.ceil(required_bottom / 2.0)))
            if args.capacity_basis == "virtual":
                base_n = max(tier_required_n, flat_required_n, args.min_n)
            else:
                base_n = max(tier_required_n, args.min_n)
            n_groups = int(math.ceil(base_n * args.capacity_scale))
            generated_bottom = 2 * n_groups
            generated_top = n_groups
            new_rows, row_span = make_btb_rows(
                n_groups,
                bottom_template,
                top_template,
                row_pitch,
                row_heights,
                args.vertical_spacing,
                orientation_pattern,
                row_y_start,
            )
            final_n_version = n_groups
        else:
            tier_required_n = "N/A"
            flat_required_n = "N/A"
            base_n = "N/A"
            n_groups = "N/A"
            generated_bottom = int(math.ceil(required_bottom * args.capacity_scale))
            generated_top = int(math.ceil(required_top * args.capacity_scale))
            if counts["BOTTOM"]:
                generated_bottom = max(generated_bottom, args.min_n)
            if counts["TOP"]:
                generated_top = max(generated_top, args.min_n)
            new_rows, row_span = make_demand_rows(
                generated_bottom,
                generated_top,
                bottom_template,
                top_template,
                row_pitch,
                row_heights,
                args.vertical_spacing,
                orientation_pattern,
                row_y_start,
            )
            final_n_version = "N/A"
    else:
        base_n = 0
        n_groups = 0
        final_n_version = 0
        generated_bottom = 0
        generated_top = 0
        new_rows = []
        row_span = 0

    final_y_max = y_min + routing_guard_band_dbu + row_span + routing_guard_band_dbu
    new_diearea = (x_min, y_min, x_max, final_y_max)
    top_util = utilization(areas["TOP"], generated_top, row_width, top_macro_height)
    bottom_util = utilization(
        areas["BOTTOM"], generated_bottom, row_width, bottom_macro_height
    )
    diearea_height = final_y_max - y_min
    if diearea_height > 0:
        flat_util = float(total_area) / float(row_width * diearea_height)
    else:
        flat_util = 0.0

    out_dir = os.path.dirname(output_def)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    write_def(def_lines, output_def, new_rows, new_diearea)

    report = {
        "version_label": args.version_label,
        "row_mode": args.row_mode,
        "vertical_spacing": args.vertical_spacing,
        "orientation_pattern": ",".join(orientation_pattern),
        "capacity_basis": args.capacity_basis,
        "input_def": input_def,
        "output_def": output_def,
        "required_top_rows": required_top,
        "required_bottom_rows": required_bottom,
        "tier_required_n": tier_required_n,
        "flat_required_height_dbu": flat_required_height,
        "flat_required_row_slots": flat_required_row_slots,
        "flat_required_n": flat_required_n,
        "base_n": base_n,
        "version_scaling_factor": args.capacity_scale,
        "final_n_version": final_n_version,
        "generated_top_rows": generated_top,
        "generated_bottom_rows": generated_bottom,
        "total_generated_rows": len(new_rows),
        "final_diearea": "( %d %d ) ( %d %d )" % new_diearea,
        "routing_guard_band_rows": args.routing_guard_band_rows,
        "routing_guard_band_dbu": routing_guard_band_dbu,
        "estimated_top_utilization": "%.6f" % top_util,
        "estimated_bottom_utilization": "%.6f" % bottom_util,
        "top_cell_count": counts["TOP"],
        "bottom_cell_count": counts["BOTTOM"],
        "top_cell_area_dbu2": areas["TOP"],
        "bottom_cell_area_dbu2": areas["BOTTOM"],
        "total_cell_area_dbu2": total_area,
        "row_width_dbu": row_width,
        "top_row_height_dbu": top_site_height,
        "bottom_row_height_dbu": bottom_site_height,
        "top_site_height_dbu": top_site_height,
        "bottom_site_height_dbu": bottom_site_height,
        "top_macro_height_dbu": top_macro_height,
        "bottom_macro_height_dbu": bottom_macro_height,
        "virtual_row_pitch_dbu": row_pitch,
        "target_utilization_for_required_rows": args.utilization,
        "target_flat_utilization": flat_utilization,
        "estimated_flat_utilization": "%.6f" % flat_util,
    }
    if report_file:
        write_report(report_file, report)

    print("Wrote:", output_def)
    if report_file:
        print("Report:", report_file)
    print("Input DEF left unchanged:", input_def)
    print("DBU/micron:", dbu)
    print("Row width DBU:", row_width)
    print("Virtual row pitch DBU:", row_pitch)
    print("Bottom row/site height DBU:", bottom_site_height)
    print("Top row/site height DBU:", top_site_height)
    print("Bottom macro capacity height DBU:", bottom_macro_height)
    print("Top macro capacity height DBU:", top_macro_height)
    print("Row mode:", args.row_mode)
    print("Vertical spacing:", args.vertical_spacing)
    print("Orientation pattern:", ",".join(orientation_pattern))
    print("Routing guard band rows:", args.routing_guard_band_rows)
    print("Routing guard band DBU:", routing_guard_band_dbu)
    print("Target utilization:", args.utilization)
    print("Target flat utilization:", flat_utilization)
    print("Bottom cells: %d, area DBU^2: %d, required_bottom_rows: %d" %
          (counts["BOTTOM"], areas["BOTTOM"], required_bottom))
    print("Top cells: %d, area DBU^2: %d, required_top_rows: %d" %
          (counts["TOP"], areas["TOP"], required_top))
    print("Total cell area DBU^2:", total_area)
    print("Flat required height DBU:", flat_required_height)
    print("Flat required row slots:", flat_required_row_slots)
    print("Flat required N groups:", flat_required_n)
    print("Tier required N groups:", tier_required_n)
    print("Base N groups:", base_n)
    print("Capacity scale:", args.capacity_scale)
    print("Final N groups:", final_n_version)
    print("Generated bottom rows:", generated_bottom)
    print("Generated top rows:", generated_top)
    print("Generated total rows:", len(new_rows))
    print("New DIEAREA:", " ".join(str(v) for v in new_diearea))
    print("Estimated bottom utilization:", "%.6f" % bottom_util)
    print("Estimated top utilization:", "%.6f" % top_util)
    print("Estimated flat utilization:", "%.6f" % flat_util)
    if missing:
        print("Warning: missing LEF definitions for %d unique masters" % len(missing))
    if unknown:
        print("Warning: could not classify tier for %d unique masters" % len(unknown))
    return 0


if __name__ == "__main__":
    sys.exit(main())
