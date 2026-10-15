#!/usr/bin/env python3
"""Report top/bottom tier balance and OpenROAD LEF compatibility for a netlist."""

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Optional, Set


def parse_lef_macros(path: Path) -> Dict[str, Optional[float]]:
    macros = {}  # type: Dict[str, Optional[float]]
    current = None  # type: Optional[str]
    for line in path.read_text(errors="ignore").splitlines():
        macro = re.match(r"\s*MACRO\s+(\S+)", line)
        if macro:
            current = macro.group(1)
            macros[current] = None
            continue
        if current:
            size = re.match(
                r"\s*SIZE\s+([0-9.]+)\s+BY\s+([0-9.]+)\s*;", line
            )
            if size:
                macros[current] = float(size.group(1)) * float(size.group(2))
                continue
            if re.match(rf"\s*END\s+{re.escape(current)}\b", line):
                current = None
    return macros


def parse_liberty_areas(path: Path) -> Dict[str, float]:
    areas = {}  # type: Dict[str, float]
    current = None  # type: Optional[str]
    depth = 0
    for raw_line in path.read_text(errors="ignore").splitlines():
        line = raw_line.split("//", 1)[0]
        if current is None:
            cell = re.match(r"\s*cell\s*\(\s*([^\s)]+)\s*\)\s*\{?", line)
            if not cell:
                continue
            current = cell.group(1)
            depth = line.count("{") - line.count("}")
            continue

        area = re.match(r"\s*area\s*:\s*([0-9.eE+-]+)\s*;", line)
        if area:
            areas[current] = float(area.group(1))

        depth += line.count("{") - line.count("}")
        if depth <= 0:
            current = None
    return areas


def strip_verilog_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//.*", "", text)


def parse_netlist_instances(path: Path, known_cells: Set[str]) -> Counter:
    text = strip_verilog_comments(path.read_text(errors="ignore"))
    counts: Counter[str] = Counter()
    instance_re = re.compile(
        r"(?m)^\s*([A-Za-z_][A-Za-z0-9_$]*)\s+"
        r"((?:\\[^\n]*?\s)|(?:[A-Za-z_][A-Za-z0-9_$]*))\s*\("
    )
    for match in instance_re.finditer(text):
        master = match.group(1)
        if master in known_cells or master.endswith(("_top_tier", "_bottom_tier")):
            counts[master] += 1
    return counts


def tier_of(master: str, top_cells: Set[str], bottom_cells: Set[str]) -> str:
    if master.endswith("_top_tier") or master in top_cells - bottom_cells:
        return "top"
    if master.endswith("_bottom_tier") or master in bottom_cells - top_cells:
        return "bottom"
    return "unknown"


def area_for(master: str, lef_areas: Dict[str, Optional[float]], lib_areas: Dict[str, float]) -> float:
    lef_area = lef_areas.get(master)
    if lef_area is not None:
        return lef_area
    return lib_areas.get(master, 0.0)


def pct(part: float, whole: float) -> float:
    return 100.0 * part / whole if whole else 0.0


def build_report(args: argparse.Namespace) -> Dict:
    top_lef = parse_lef_macros(Path(args.top_lef))
    bottom_lef = parse_lef_macros(Path(args.bottom_lef))
    top_lib = parse_liberty_areas(Path(args.top_liberty))
    bottom_lib = parse_liberty_areas(Path(args.bottom_liberty))

    top_cells = set(top_lib)
    bottom_cells = set(bottom_lib)
    known_cells = top_cells | bottom_cells | set(top_lef) | set(bottom_lef)
    counts = parse_netlist_instances(Path(args.verilog), known_cells)

    lef_areas = {**top_lef, **bottom_lef}
    lib_areas = {**top_lib, **bottom_lib}
    physical_masters = set(top_lef) | set(bottom_lef)

    tier_counts = Counter()
    tier_area = defaultdict(float)
    missing = Counter()
    masters = []

    for master, count in counts.items():
        tier = tier_of(master, top_cells, bottom_cells)
        one_area = area_for(master, lef_areas, lib_areas)
        tier_counts[tier] += count
        tier_area[tier] += one_area * count
        if master not in physical_masters:
            missing[master] += count
        masters.append(
            {
                "master": master,
                "tier": tier,
                "count": count,
                "area_each": one_area,
                "total_area": one_area * count,
                "has_lef": master in physical_masters,
            }
        )

    total_count = sum(counts.values())
    total_area = sum(tier_area.values())
    missing_count = sum(missing.values())
    masters.sort(key=lambda row: (-row["count"], row["master"]))

    return {
        "verilog": str(args.verilog),
        "top_lef": str(args.top_lef),
        "bottom_lef": str(args.bottom_lef),
        "top_liberty": str(args.top_liberty),
        "bottom_liberty": str(args.bottom_liberty),
        "top_lef_macro_count": len(top_lef),
        "bottom_lef_macro_count": len(bottom_lef),
        "top_liberty_cell_count": len(top_lib),
        "bottom_liberty_cell_count": len(bottom_lib),
        "total_instances": total_count,
        "top_instances": tier_counts["top"],
        "bottom_instances": tier_counts["bottom"],
        "unknown_instances": tier_counts["unknown"],
        "top_area": tier_area["top"],
        "bottom_area": tier_area["bottom"],
        "unknown_area": tier_area["unknown"],
        "total_area": total_area,
        "top_area_pct": pct(tier_area["top"], total_area),
        "bottom_area_pct": pct(tier_area["bottom"], total_area),
        "missing_physical_master_instances": missing_count,
        "missing_physical_master_pct": pct(missing_count, total_count),
        "missing_physical_masters": [
            {"master": master, "count": count}
            for master, count in missing.most_common()
        ],
        "masters": masters,
    }


def write_text_report(report: Dict, path: Path) -> None:
    lines = [
        "Tier balance and OpenROAD physical-master report",
        "=" * 55,
        f"verilog: {report['verilog']}",
        f"top_lef: {report['top_lef']}",
        f"bottom_lef: {report['bottom_lef']}",
        f"top_liberty: {report['top_liberty']}",
        f"bottom_liberty: {report['bottom_liberty']}",
        "",
        f"top_lef_macro_count: {report['top_lef_macro_count']}",
        f"bottom_lef_macro_count: {report['bottom_lef_macro_count']}",
        f"top_liberty_cell_count: {report['top_liberty_cell_count']}",
        f"bottom_liberty_cell_count: {report['bottom_liberty_cell_count']}",
        "",
        f"total_instances: {report['total_instances']}",
        f"top_instances: {report['top_instances']}",
        f"bottom_instances: {report['bottom_instances']}",
        f"unknown_instances: {report['unknown_instances']}",
        f"top_area: {report['top_area']:.6f}",
        f"bottom_area: {report['bottom_area']:.6f}",
        f"unknown_area: {report['unknown_area']:.6f}",
        f"total_area: {report['total_area']:.6f}",
        f"top_area_pct: {report['top_area_pct']:.3f}",
        f"bottom_area_pct: {report['bottom_area_pct']:.3f}",
        "",
        f"missing_physical_master_instances: {report['missing_physical_master_instances']}",
        f"missing_physical_master_pct: {report['missing_physical_master_pct']:.3f}",
        "",
        "Missing physical masters by instance count:",
    ]
    for item in report["missing_physical_masters"][:80]:
        lines.append(f"  {item['count']:8d} {item['master']}")

    lines.extend(["", "Masters by instance count:"])
    for item in report["masters"][:160]:
        flag = "LEF" if item["has_lef"] else "NO_LEF"
        lines.append(
            f"  {item['count']:8d} {item['tier']:7s} {flag:6s} "
            f"{item['area_each']:12.6f} {item['master']}"
        )

    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verilog", required=True)
    parser.add_argument("--top-liberty", required=True)
    parser.add_argument("--bottom-liberty", required=True)
    parser.add_argument("--top-lef", required=True)
    parser.add_argument("--bottom-lef", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--json")
    args = parser.parse_args()

    report = build_report(args)
    write_text_report(report, Path(args.report))
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {args.report}")
    if args.json:
        print(f"Wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
