#!/usr/bin/env python3
"""Verify the shipped monolithic 3D inputs (Python standard library only).

    python3 setup.py           verify data/ and pdk/ against data/manifest.json
    python3 setup.py --update  regenerate data/manifest.json after an intentional change
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / 'data' / 'manifest.json'
TRACKED = ('data/netlists', 'data/netlists_2d', 'pdk')
METADATA = {
    'configurations': ['RocketConfig', 'DualRocketConfig', 'QuadRocketConfig'],
    'synthesis_tool': 'Cadence Genus 23.11-s100_1 (DualRocket netlist header)',
    'technology': 'Nangate 45 nm, bottom/top tier views for the 3D flows',
    'reference_openroad': 'v2.0-21011-gbb2a3e831',
}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def collect():
    files = {}
    for top in TRACKED:
        for path in sorted((HERE / top).rglob('*')):
            if path.is_file():
                files[path.relative_to(HERE).as_posix()] = digest(path)
    return files


def main():
    if '--update' in sys.argv[1:]:
        manifest = dict(METADATA, files=collect())
        MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
        print('Wrote %s (%d files)' % (MANIFEST.relative_to(HERE), len(manifest['files'])))
        return
    expected = json.loads(MANIFEST.read_text())['files']
    actual = collect()
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    changed = sorted(n for n in set(expected) & set(actual) if expected[n] != actual[n])
    for label, names in (('Missing', missing), ('Unlisted', extra), ('Checksum mismatch', changed)):
        for name in names:
            print('%s: %s' % (label, name))
    if missing or changed:
        raise SystemExit('Input verification failed')
    print('Inputs verified: %d files%s.' % (len(expected), '; unlisted files present' if extra else ''))


if __name__ == '__main__':
    main()
