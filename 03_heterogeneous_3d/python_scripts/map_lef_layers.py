#!/usr/bin/env python3
"""Create a derived LEF with selected layer names remapped.

This is intended for route-evaluation abstractions. It preserves all other
content and refuses to overwrite an existing output.
"""

import argparse
import os


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-lef", required=True)
    parser.add_argument("--output-lef", required=True)
    parser.add_argument(
        "--map",
        action="append",
        required=True,
        metavar="OLD=NEW",
        help="Layer-name mapping. May be passed more than once.",
    )
    return parser.parse_args()


def parse_mapping(items):
    mapping = []
    for item in items:
        if "=" not in item:
            raise SystemExit("--map must use OLD=NEW form: %s" % item)
        old, new = item.split("=", 1)
        if not old or not new:
            raise SystemExit("--map must use non-empty OLD=NEW form: %s" % item)
        mapping.append((old, new))
    return mapping


def main():
    args = parse_args()
    input_lef = os.path.abspath(args.input_lef)
    output_lef = os.path.abspath(args.output_lef)
    mapping = parse_mapping(args.map)

    if input_lef == output_lef:
        raise SystemExit("Refusing to overwrite input LEF")
    if os.path.exists(output_lef):
        raise SystemExit("Output LEF already exists: %s" % output_lef)

    out_dir = os.path.dirname(output_lef)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    replacements = 0
    with open(input_lef) as fin, open(output_lef, "w") as fout:
        for line in fin:
            new_line = line
            for old, new in mapping:
                count = new_line.count(old)
                if count:
                    replacements += count
                    new_line = new_line.replace(old, new)
            fout.write(new_line)

    print("Wrote:", output_lef)
    print("Layer replacements:", replacements)
    for old, new in mapping:
        print("%s -> %s" % (old, new))


if __name__ == "__main__":
    main()
