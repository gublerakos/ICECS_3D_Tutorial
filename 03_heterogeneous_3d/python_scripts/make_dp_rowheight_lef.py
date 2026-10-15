#!/usr/bin/env python3
"""Create a test LEF with macro height decoupled from virtual row height.

This preserves macro names, pins, layers, and shapes. It only changes:
  - macro SIZE Y
  - macro ORIGIN Y, centered relative to the old macro height
  - matching SITE SIZE Y, only when --site-height is provided
"""

import argparse
import os
import re


def fmt(value):
    text = "%.3f" % value
    return text.rstrip("0").rstrip(".") if "." in text else text


def rewrite_size_y(line, height):
    match = re.match(r"^(\s*SIZE\s+[-0-9.]+\s+BY\s+)([-0-9.]+)(\s*;.*)$", line)
    if not match:
        return line
    return "%s%s%s\n" % (match.group(1), fmt(height), match.group(3))


def rewrite_macro_block(lines, target_height):
    size_re = re.compile(r"^(\s*SIZE\s+[-0-9.]+\s+BY\s+)([-0-9.]+)(\s*;.*)$")
    origin_re = re.compile(r"^(\s*ORIGIN\s+[-0-9.]+\s+)([-0-9.]+)(\s*;.*)$")
    class_re = re.compile(r"^\s*CLASS\s+.*;")

    old_height = None
    has_origin = False
    for line in lines:
        size_match = size_re.match(line)
        if size_match:
            old_height = float(size_match.group(2))
        if origin_re.match(line):
            has_origin = True

    if old_height is None:
        return lines, None

    centered_origin = (target_height - old_height) / 2.0
    rewritten = []
    inserted_origin = False

    for line in lines:
        origin_match = origin_re.match(line)
        if origin_match:
            rewritten.append(
                "%s%s%s\n" % (origin_match.group(1), fmt(centered_origin), origin_match.group(3))
            )
            inserted_origin = True
            continue

        rewritten.append(rewrite_size_y(line, target_height) if size_re.match(line) else line)

        if not has_origin and not inserted_origin and class_re.match(line):
            rewritten.append("  ORIGIN 0 %s ;\n" % fmt(centered_origin))
            inserted_origin = True

    return rewritten, centered_origin


def collect_macro_sites(input_lef):
    macro_start_re = re.compile(r"^\s*MACRO\s+(\S+)")
    macro_end_re = re.compile(r"^\s*END\s+(\S+)\s*$")
    site_re = re.compile(r"^\s*SITE\s+(\S+)\s*;")

    sites = set()
    in_macro = False
    macro_name = None

    with open(input_lef) as fin:
        for line in fin:
            macro_start = macro_start_re.match(line)
            if macro_start:
                in_macro = True
                macro_name = macro_start.group(1)
                continue

            if not in_macro:
                continue

            site_match = site_re.match(line)
            if site_match:
                sites.add(site_match.group(1))

            macro_end = macro_end_re.match(line)
            if macro_end and macro_end.group(1) == macro_name:
                in_macro = False
                macro_name = None

    return sites


def convert(input_lef, output_lef, target_height, site_height=None):
    macro_start_re = re.compile(r"^\s*MACRO\s+(\S+)")
    macro_end_re = re.compile(r"^\s*END\s+(\S+)\s*$")
    site_start_re = re.compile(r"^\s*SITE\s+(\S+)")
    site_end_re = re.compile(r"^\s*END\s+(\S+)\s*$")

    macro_count = 0
    origins = set()
    sites_to_update = collect_macro_sites(input_lef)
    in_macro = False
    macro_name = None
    macro_lines = []
    in_site = False
    site_name = None

    with open(input_lef) as fin, open(output_lef, "w") as fout:
        for line in fin:
            macro_start = macro_start_re.match(line)
            if macro_start:
                in_macro = True
                macro_name = macro_start.group(1)
                macro_lines = [line]
                continue

            if in_macro:
                macro_lines.append(line)
                macro_end = macro_end_re.match(line)
                if macro_end and macro_end.group(1) == macro_name:
                    rewritten, origin = rewrite_macro_block(macro_lines, target_height)
                    if origin is not None:
                        macro_count += 1
                        origins.add(round(origin, 6))
                    fout.writelines(rewritten)
                    in_macro = False
                    macro_name = None
                    macro_lines = []
                continue

            site_start = site_start_re.match(line)
            if site_start:
                in_site = True
                site_name = site_start.group(1)
                fout.write(line)
                continue

            if in_site:
                if site_height is not None and site_name in sites_to_update:
                    fout.write(rewrite_size_y(line, site_height))
                else:
                    fout.write(line)
                site_end = site_end_re.match(line)
                if site_end and site_end.group(1) == site_name:
                    in_site = False
                    site_name = None
                continue

            fout.write(line)

    return macro_count, sorted(origins)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-lef", required=True)
    parser.add_argument("--output-lef", required=True)
    parser.add_argument(
        "--target-height",
        type=float,
        required=True,
        help="Macro cell height to write into MACRO SIZE statements.",
    )
    parser.add_argument(
        "--site-height",
        type=float,
        help=(
            "Virtual row/site height to write into SITE SIZE statements. "
            "If omitted, SITE blocks are preserved."
        ),
    )
    args = parser.parse_args()

    if os.path.abspath(args.input_lef) == os.path.abspath(args.output_lef):
        raise SystemExit("Refusing to overwrite input LEF")
    if os.path.exists(args.output_lef):
        raise SystemExit("Output LEF already exists: %s" % args.output_lef)

    out_dir = os.path.dirname(os.path.abspath(args.output_lef))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    macro_count, origins = convert(
        args.input_lef,
        args.output_lef,
        args.target_height,
        site_height=args.site_height,
    )
    print("Wrote:", args.output_lef)
    print("Macros converted:", macro_count)
    print("Target macro height:", fmt(args.target_height))
    if args.site_height is not None:
        print("Virtual site height:", fmt(args.site_height))
    print("Centered origins:", ", ".join(fmt(x) for x in origins))


if __name__ == "__main__":
    main()
