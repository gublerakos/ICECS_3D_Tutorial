#!/usr/bin/env python3
"""Prepare CVA6 RTL and apply the VGA v5 post-map area-balancing algorithm."""
import json
import math
import os
from pathlib import Path
import re
import sys
import shlex
import itertools
from types import SimpleNamespace

from report_tier_balance import (build_report, parse_lef_macros,
                                 parse_liberty_areas, strip_verilog_comments,
                                 write_text_report)
from rewrite_mapped_netlist_tiers import (bottom_to_top_master, choose_top_instances,
                                        parse_instances, write_report)

HERE = Path(__file__).resolve().parent



def fail(message):
    raise SystemExit(message)


def positive(name):
    value = float(os.environ[name])
    if not math.isfinite(value) or value <= 0:
        fail(name + ' must be finite and positive')
    return value


def groups(text, kind):
    """Read balanced Liberty groups; braces inside quoted strings are ignored."""
    pattern = re.compile(r'\b' + kind + r'\s*\(([^)]*)\)\s*\{')
    for match in pattern.finditer(text):
        depth, quoted, escaped = 1, False, False
        for end in range(match.end(), len(text)):
            char = text[end]
            if escaped:
                escaped = False
            elif char == '\\' and quoted:
                escaped = True
            elif char == '"':
                quoted = not quoted
            elif not quoted:
                depth += (char == '{') - (char == '}')
            if depth == 0:
                yield match.group(1).strip().strip('"'), text[match.end():end]
                break
        else:
            fail('Unbalanced Liberty group: ' + match.group(0))


def boolean_key(expression):
    """Truth-table signature for the Liberty Boolean grammar used by these PDKs.

    Unsupported syntax stays a literal key and cannot enable an unsafe swap.
    """
    tokens = re.findall(r'[A-Za-z_][\w$]*|[01!~&*|+^()\x27]', expression)
    if ''.join(tokens) != expression:
        return ('literal', expression)
    position = [0]
    precedence = {'|': 1, '+': 1, '^': 2, '&': 3, '*': 3}

    def parse(minimum=0):
        if position[0] >= len(tokens):
            raise ValueError('Incomplete expression')
        token = tokens[position[0]]
        position[0] += 1
        if token in ('!', '~'):
            node = ('not', parse(4))
        elif token == '(':
            node = parse()
            if position[0] >= len(tokens) or tokens[position[0]] != ')':
                raise ValueError('Unbalanced expression')
            position[0] += 1
        elif re.fullmatch(r'[A-Za-z_][\w$]*|[01]', token):
            node = ('atom', token)
        else:
            raise ValueError('Unsupported expression')
        while position[0] < len(tokens):
            op = tokens[position[0]]
            if op == "'":
                position[0] += 1
                node = ('not', node)
            elif op in precedence and precedence[op] >= minimum:
                position[0] += 1
                node = (op, node, parse(precedence[op] + 1))
            else:
                break
        return node

    def evaluate(node, values):
        op = node[0]
        if op == 'atom':
            return values[node[1]] if node[1] not in ('0', '1') else node[1] == '1'
        if op == 'not':
            return not evaluate(node[1], values)
        a, b = evaluate(node[1], values), evaluate(node[2], values)
        return (a and b) if op in ('&', '*') else ((a or b) if op in ('|', '+') else a != b)

    try:
        tree = parse()
        names = tuple(sorted(set(re.findall(r'[A-Za-z_][\w$]*', expression))))
        if position[0] != len(tokens) or len(names) > 10:
            raise ValueError('Unsupported expression')
        return (names, tuple(evaluate(tree, dict(zip(names, values)))
                             for values in itertools.product((False, True), repeat=len(names))))
    except ValueError:
        return ('literal', expression)


def signatures(path, text=None):
    text = strip_verilog_comments(path.read_text() if text is None else text)
    result = {}
    for cell, body in groups(text, 'cell'):
        pins = []
        for pin, pinbody in groups(body, 'pin'):
            attrs = []
            for key in ('direction', 'function', 'three_state', 'clock'):
                match = re.search(r'\b' + key + r'\s*:\s*([^;]+);', pinbody)
                value = re.sub(r'\s+', '', match.group(1)).strip('"') if match else ''
                attrs.append(boolean_key(value) if value and key in ('function', 'three_state') else value)
            pins.append((pin, tuple(attrs)))
        state = []
        for kind in ('ff', 'latch'):
            for name, statebody in groups(body, kind):
                attrs = re.findall(r'(\w+)\s*:\s*([^;]+);', statebody)
                state.append((kind, re.sub(r'\s+', '', name), tuple(sorted(
                    (key, boolean_key(re.sub(r'\s+', '', value).strip('"'))) for key, value in attrs))))
        result[cell] = (tuple(sorted(pins)), tuple(state))
    return result


def bottom_library_text(path):
    text = path.read_text()
    # Change declaration names only: functions, pins, and timing are untouched.
    return re.sub(r'(\bcell\s*\(\s*)([A-Za-z_][\w$]*)(\s*\))',
                  lambda m: m[1] + (m[2] if m[2].endswith('_bottom_tier') else
                                    m[2] + '_bottom_tier') + m[3], text)


def renamed_boolean(key, mapping):
    if not isinstance(key, tuple) or key[0] == 'literal':
        return key
    names, values = key
    new_names = tuple(sorted(mapping.get(n, n) for n in names))
    table = []
    for bits in itertools.product((False, True), repeat=len(new_names)):
        lookup = dict(zip(new_names, bits))
        index = 0
        for name in names:
            index = 2 * index + lookup[mapping.get(name, name)]
        table.append(values[index])
    return (new_names, tuple(table))


def matching_pin_map(bottom, top):
    # Sequential cells require identical signatures; different sequential cell
    # families are not substituted. Combinational renaming is proven by truth tables.
    if bottom == top:
        return {name: name for name, _ in bottom[0]}
    if bottom[1] or top[1]:
        return None
    if any(isinstance(a, tuple) and a[0] == 'literal'
           for signature in (bottom, top) for _, attrs in signature[0] for a in attrs):
        return None
    bins = [name for name, a in bottom[0] if a[0] == 'input']
    tins = [name for name, a in top[0] if a[0] == 'input']
    bouts = [name for name, a in bottom[0] if a[0] == 'output']
    touts = [name for name, a in top[0] if a[0] == 'output']
    if (len(bins) != len(tins) or len(bouts) != len(touts) or
            len(bins) + len(bouts) != len(bottom[0]) or
            len(tins) + len(touts) != len(top[0]) or len(bins) > 6):
        return None
    for inputs in itertools.permutations(tins):
        for outputs in itertools.permutations(touts):
            mapping = dict(zip(bins + bouts, list(inputs) + list(outputs)))
            renamed = tuple(sorted((mapping[name], (attrs[0],
                renamed_boolean(attrs[1], mapping), renamed_boolean(attrs[2], mapping), attrs[3]))
                for name, attrs in bottom[0]))
            if renamed == top[0]:
                return mapping
    return None


def physical_pins(path):
    result, current = {}, None
    for line in path.read_text().splitlines():
        words = line.split()
        if len(words) == 2 and words[0] == 'MACRO':
            current = words[1]
            result[current] = set()
        elif current and len(words) == 2 and words[0] == 'PIN':
            result[current].add(words[1])
        elif current and words == ['END', current]:
            current = None
    return result


def libraries():
    paths = {key: Path(os.environ[key]) for key in
             ('TOP_LIBERTY', 'BOTTOM_LIBERTY', 'TOP_LEF', 'BOTTOM_LEF')}
    for key, path in paths.items():
        if not path.is_file():
            fail('Missing {}: {}'.format(key, path))
    top = parse_liberty_areas(paths['TOP_LIBERTY'])
    bottom_text = bottom_library_text(paths['BOTTOM_LIBERTY'])
    bottom = {}
    for name, body in groups(strip_verilog_comments(bottom_text), 'cell'):
        if name in bottom:
            fail('Duplicate bottom library cell: ' + name)
        match = re.search(r'\barea\s*:\s*([\d.eE+-]+)', body)
        if match:
            bottom[name] = float(match[1])
    top_lef = parse_lef_macros(paths['TOP_LEF'])
    bottom_lef = parse_lef_macros(paths['BOTTOM_LEF'])
    ts = signatures(paths['TOP_LIBERTY'])
    bs = signatures(paths['BOTTOM_LIBERTY'], bottom_text)
    # Require every logical signal pin to exist in the corresponding LEF.
    for area_table, sigs, path in ((top_lef, ts, paths['TOP_LEF']),
                                   (bottom_lef, bs, paths['BOTTOM_LEF'])):
        pins = physical_pins(path)
        for cell in list(area_table):
            if cell in sigs and not {name for name, _ in sigs[cell][0]} <= pins.get(cell, set()):
                del area_table[cell]
    compatible = set()
    pin_maps = {}
    for cell in bottom:
        other = bottom_to_top_master(cell)
        if other in top and top_lef.get(other, 0) and bottom_lef.get(cell, 0):
            mapping = matching_pin_map(bs[cell], ts[other])
            if mapping is not None:
                compatible.add(other)
                pin_maps[cell] = mapping
    if not compatible:
        fail('No pin/function/state-compatible cell pairs with LEF views')
    for table in (top, bottom, top_lef, bottom_lef):
        if not table or any(a is None or not math.isfinite(a) or a <= 0 for a in table.values()):
            fail('Empty library or missing/nonpositive cell area')
    print('Libraries: {} compatible top masters; balancing native LEF areas'.format(len(compatible)))
    return paths, top, bottom, top_lef, bottom_lef, compatible, pin_maps


def partition():
    out = Path(os.environ['OUT'])
    paths, top, bottom, top_lef, bottom_lef, compatible, pin_maps = libraries()
    src = out / 'cva6_bottom_reference.v'
    text = src.read_text()
    clean = strip_verilog_comments(text)
    modules = re.findall(r'\bmodule\s+([A-Za-z_][\w$]*)', clean)
    if modules != ['cva6']:
        fail('Expected one flat cva6 module, got: ' + repr(modules))
    # Reject blackboxes, unmapped cells, and unsupported instance syntax rather
    # than silently ignoring them as the original VGA helper did.
    declarations = re.findall(r'(?m)^\s*([A-Za-z_][\w$]*)\s+'
                              r'(?:\\[^\n]*?\s|[A-Za-z_][\w$]*)\s*\(', clean)
    unknown = set(declarations) - set(bottom) - {'module'}
    if unknown:
        fail('Unmapped/unknown instance masters: ' + ', '.join(sorted(unknown)))
    insts = parse_instances(text, bottom, top, compatible, 'lef')
    if not insts or len(insts) != len(declarations) - 1:
        fail('Mapped instance coverage failed; inspect reference netlist syntax')
    missing = {i.master for i in insts if i.master not in bottom_lef}
    if missing:
        fail('Bottom cells without LEF: ' + ', '.join(sorted(missing)))
    # Same VGA v5 greedy algorithm; costs use native physical footprints.
    insts = [i._replace(bottom_area=bottom_lef[i.master],
                        top_area=top_lef[i.top_master] if i.top_master else 0) for i in insts]
    scale = positive('TOP_AREA_SCALE')
    selected = choose_top_instances(insts, scale, 'balance')
    if not selected or len(selected) == len(insts):
        fail('One tier is empty')
    atop = sum(i.top_area for i in insts if i.index in selected)
    abot = sum(i.bottom_area for i in insts if i.index not in selected)
    imbalance = abs(atop * scale - abot) / max(atop * scale, abot)
    if imbalance > positive('MAX_IMBALANCE'):
        fail('Area imbalance {:.3%} exceeds MAX_IMBALANCE; no final netlist published'.format(imbalance))
    dst = out / 'cva6_heterogeneous.v'
    if dst.exists():
        fail('Refusing to overwrite ' + str(dst))
    # Rewrite only master names and named pin identifiers. Net expressions and
    # instance names are retained byte-for-byte, including escaped identifiers.
    edits = []
    for inst in insts:
        if inst.index not in selected:
            continue
        edits.append((inst.master_start, inst.master_end, inst.top_master))
        end = text.find(';', inst.master_end)
        if end < 0:
            fail('Unterminated instance: ' + inst.inst_name)
        pins = list(re.finditer(r'(?<=[(,\s])\.([A-Za-z_][\w$]*)\s*\(', text[inst.master_end:end]))
        if not pins:
            fail('Expected named pin connections: ' + inst.inst_name)
        for pin in pins:
            old = pin.group(1)
            if old not in pin_maps[inst.master]:
                fail('Unknown pin {} on {}'.format(old, inst.master))
            edits.append((inst.master_end + pin.start(1), inst.master_end + pin.end(1),
                          pin_maps[inst.master][old]))
    chunks, cursor = [], 0
    for start, end, replacement in sorted(edits):
        chunks.extend((text[cursor:start], replacement))
        cursor = end
    chunks.append(text[cursor:])
    rewritten = ''.join(chunks)
    mapped = parse_instances(rewritten, dict(bottom, **top), top, compatible, 'lef')
    if len(mapped) != len(insts):
        fail('Instance count changed during rewrite')
    for before, after in zip(insts, mapped):
        expected = before.top_master if before.index in selected else before.master
        if after.master != expected or after.inst_name != before.inst_name:
            fail('Instance mapping changed unexpectedly')
    dst.write_text(rewritten)
    write_report(out / 'partition.rpt', insts, selected, scale, 'balance', 'lef')
    args = SimpleNamespace(verilog=str(dst), top_liberty=str(paths['TOP_LIBERTY']),
                           bottom_liberty=str(out / 'bottom_15nm.lib'),
                           top_lef=str(paths['TOP_LEF']), bottom_lef=str(paths['BOTTOM_LEF']))
    report = build_report(args)
    report['effective_area_imbalance'] = imbalance
    report['top_area_scale'] = scale
    write_text_report(report, out / 'tier_balance.rpt')
    (out / 'tier_balance.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Final netlist: {}\nTOP area={:.6f}; BOTTOM area={:.6f}; effective imbalance={:.3%}'.format(
        dst, atop, abot, imbalance))


