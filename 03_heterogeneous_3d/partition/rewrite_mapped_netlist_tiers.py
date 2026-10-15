#!/usr/bin/env python3
"""Rewrite a mapped all-bottom netlist into an area-balanced two-tier netlist."""

import argparse
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Set

from report_tier_balance import parse_lef_macros, parse_liberty_areas


class Instance(NamedTuple):
    index: int
    master: str
    inst_name: str
    master_start: int
    master_end: int
    top_master: Optional[str]
    bottom_area: float
    top_area: float
    is_sequential: bool


def strip_escaped_instance_name(raw: str) -> str:
    raw = raw.strip()
    if raw.endswith("("):
        raw = raw[:-1].strip()
    return raw


def bottom_to_top_master(master: str) -> str:
    if master.endswith("_bottom_tier"):
        return master[: -len("_bottom_tier")] + "_top_tier"
    return master + "_top_tier"


def is_sequential_master(master: str) -> bool:
    base = master
    for suffix in ("_bottom_tier", "_top_tier"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
    return bool(re.search(r"(DFF|SDFF|LAT|LATCH)", base, flags=re.IGNORECASE))


def parse_instances(text: str, bottom_areas: Dict[str, float],
                    top_areas: Dict[str, float],
                    top_physical_masters: Set[str],
                    top_physical_mode: str) -> List[Instance]:
    instance_re = re.compile(
        r"(?m)^(?P<indent>\s*)"
        r"(?P<master>[A-Za-z_][A-Za-z0-9_$]*)"
        r"\s+"
        r"(?P<inst>(?:\\[^\n]*?\s)|(?:[A-Za-z_][A-Za-z0-9_$]*))"
        r"\s*\("
    )

    instances: List[Instance] = []
    for match in instance_re.finditer(text):
        master = match.group("master")
        if master not in bottom_areas:
            continue

        top_master = bottom_to_top_master(master)
        if top_master not in top_areas:
            top_master = None
        if (
            top_master is not None
            and top_physical_mode == "lef"
            and top_master not in top_physical_masters
        ):
            top_master = None

        instances.append(
            Instance(
                index=len(instances),
                master=master,
                inst_name=strip_escaped_instance_name(match.group("inst")),
                master_start=match.start("master"),
                master_end=match.end("master"),
                top_master=top_master,
                bottom_area=bottom_areas.get(master, 0.0),
                top_area=top_areas.get(top_master, 0.0) if top_master else 0.0,
                is_sequential=is_sequential_master(master),
            )
        )
    return instances


def choose_top_instances(instances: List[Instance], top_area_scale: float,
                         sequential_policy: str) -> Set[int]:
    top_indices: Set[int] = set()
    top_effective = 0.0
    bottom_effective = 0.0

    def sortable_area(inst: Instance) -> float:
        if not inst.top_master:
            return inst.bottom_area
        return max(inst.bottom_area, inst.top_area * top_area_scale)

    ordered = sorted(
        instances,
        key=lambda inst: (-sortable_area(inst), inst.inst_name, inst.index),
    )

    # Account for all forced assignments before balancing movable instances.
    # Otherwise small nonconvertible cells encountered late bias the result.
    movable = []
    for inst in ordered:
        if not inst.top_master or (sequential_policy == "bottom" and inst.is_sequential):
            bottom_effective += inst.bottom_area
        elif sequential_policy == "top" and inst.is_sequential:
            top_indices.add(inst.index)
            top_effective += inst.top_area * top_area_scale
        else:
            movable.append(inst)

    for inst in movable:
        if not inst.top_master:
            bottom_effective += inst.bottom_area
            continue
        if sequential_policy == "bottom" and inst.is_sequential:
            bottom_effective += inst.bottom_area
            continue
        if sequential_policy == "top" and inst.is_sequential:
            top_indices.add(inst.index)
            top_effective += inst.top_area * top_area_scale
            continue

        diff_if_top = abs((top_effective + inst.top_area * top_area_scale) - bottom_effective)
        diff_if_bottom = abs(top_effective - (bottom_effective + inst.bottom_area))
        if diff_if_top <= diff_if_bottom:
            top_indices.add(inst.index)
            top_effective += inst.top_area * top_area_scale
        else:
            bottom_effective += inst.bottom_area

    return top_indices


def rewrite_text(text: str, instances: List[Instance], top_indices: Set[int]) -> str:
    replacements = []
    for inst in instances:
        if inst.index in top_indices and inst.top_master:
            replacements.append((inst.master_start, inst.master_end, inst.top_master))

    out = []
    cursor = 0
    for start, end, replacement in sorted(replacements):
        out.append(text[cursor:start])
        out.append(replacement)
        cursor = end
    out.append(text[cursor:])
    return "".join(out)


def write_report(path: Path, instances: List[Instance], top_indices: Set[int],
                 top_area_scale: float, sequential_policy: str,
                 top_physical_mode: str) -> None:
    top_count = 0
    bottom_count = 0
    top_area = 0.0
    bottom_area = 0.0
    top_effective = 0.0
    bottom_effective = 0.0
    convertible = 0
    nonconvertible = 0
    forced_bottom_seq = 0
    top_masters: Counter[str] = Counter()
    bottom_masters: Counter[str] = Counter()

    for inst in instances:
        if inst.top_master:
            convertible += 1
        else:
            nonconvertible += 1

        if inst.index in top_indices and inst.top_master:
            top_count += 1
            top_area += inst.top_area
            top_effective += inst.top_area * top_area_scale
            top_masters[inst.top_master] += 1
        else:
            bottom_count += 1
            bottom_area += inst.bottom_area
            bottom_effective += inst.bottom_area
            bottom_masters[inst.master] += 1
            if sequential_policy == "bottom" and inst.is_sequential:
                forced_bottom_seq += 1

    lines = [
        "mapped_netlist_tier_rewrite_report",
        "=" * 42,
        f"top_area_scale: {top_area_scale}",
        f"sequential_policy: {sequential_policy}",
        f"top_physical_mode: {top_physical_mode}",
        f"total_instances: {len(instances)}",
        f"convertible_to_top_instances: {convertible}",
        f"nonconvertible_instances: {nonconvertible}",
        f"assigned_top_count: {top_count}",
        f"assigned_bottom_count: {bottom_count}",
        f"forced_bottom_sequential_count: {forced_bottom_seq}",
        f"top_area: {top_area:.6f}",
        f"bottom_area: {bottom_area:.6f}",
        f"top_effective_area: {top_effective:.6f}",
        f"bottom_effective_area: {bottom_effective:.6f}",
    ]
    if top_effective:
        lines.append(f"bottom_over_top_effective_area_ratio: {bottom_effective / top_effective:.6f}")
    if top_area + bottom_area:
        lines.append(f"top_area_pct: {100.0 * top_area / (top_area + bottom_area):.3f}")
        lines.append(f"bottom_area_pct: {100.0 * bottom_area / (top_area + bottom_area):.3f}")

    lines.extend(["", "Top masters by count:"])
    for master, count in top_masters.most_common(80):
        lines.append(f"  {count:8d} {master}")

    lines.extend(["", "Bottom masters by count:"])
    for master, count in bottom_masters.most_common(80):
        lines.append(f"  {count:8d} {master}")

    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--top-liberty", required=True)
    parser.add_argument("--bottom-liberty", required=True)
    parser.add_argument("--top-lef")
    parser.add_argument("--report", required=True)
    parser.add_argument("--top-area-scale", type=float, default=1.0)
    parser.add_argument(
        "--sequential-policy",
        choices=("balance", "bottom", "top"),
        default="balance",
        help="How to treat sequential instances while assigning tiers.",
    )
    parser.add_argument(
        "--top-physical-mode",
        choices=("lib", "lef"),
        default="lib",
        help="Use 'lef' to assign only top masters present in the top LEF.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    report_path = Path(args.report)

    for path in (output_path, report_path):
        if path.exists():
            raise SystemExit(f"Refusing to overwrite existing file: {path}")

    top_areas = parse_liberty_areas(Path(args.top_liberty))
    bottom_areas = parse_liberty_areas(Path(args.bottom_liberty))
    top_physical_masters: Set[str] = set()
    if args.top_lef:
        top_physical_masters = set(parse_lef_macros(Path(args.top_lef)))

    text = input_path.read_text(errors="ignore")
    instances = parse_instances(
        text,
        bottom_areas=bottom_areas,
        top_areas=top_areas,
        top_physical_masters=top_physical_masters,
        top_physical_mode=args.top_physical_mode,
    )
    if not instances:
        raise SystemExit(f"No mapped bottom-tier instances found in {input_path}")

    top_indices = choose_top_instances(
        instances,
        top_area_scale=args.top_area_scale,
        sequential_policy=args.sequential_policy,
    )
    output_path.write_text(rewrite_text(text, instances, top_indices))
    write_report(
        report_path,
        instances=instances,
        top_indices=top_indices,
        top_area_scale=args.top_area_scale,
        sequential_policy=args.sequential_policy,
        top_physical_mode=args.top_physical_mode,
    )

    print(f"Wrote {output_path}")
    print(f"Wrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
