#!/usr/bin/env python3
"""Verify the shipped CVA6 input and unpack it once (Python standard library only)."""
import gzip
import hashlib
import json
from pathlib import Path
import os
import shutil
import tempfile

HERE = Path(__file__).resolve().parent

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def main():
    data = HERE / 'data'
    manifest = json.loads((data / 'manifest.json').read_text())
    source = data / (manifest['netlist'] + '.gz')
    target = data / manifest['netlist']
    if digest(source) != manifest['compressed_sha256']:
        raise SystemExit('Compressed CVA6 input checksum mismatch')
    if digest(data / 'cva6.sdc') != manifest['sdc_sha256']:
        raise SystemExit('SDC checksum mismatch')
    for name, entry in json.loads((HERE / 'pdk/provenance.json').read_text()).items():
        if digest(HERE / 'pdk' / name) != entry['sha256']:
            raise SystemExit('PDK checksum mismatch: ' + name)
    if target.exists():
        if digest(target) != manifest['sha256']:
            raise SystemExit('Existing netlist differs; preserve it elsewhere before unpacking')
        print('Inputs verified; CVA6 is already unpacked.')
        return
    fd, temporary = tempfile.mkstemp(prefix='.unpack-', dir=data)
    try:
        with os.fdopen(fd, 'wb') as out, gzip.open(source, 'rb') as inp:
            shutil.copyfileobj(inp, out)
        if digest(Path(temporary)) != manifest['sha256']:
            raise SystemExit('Unpacked CVA6 checksum mismatch')
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print('Inputs verified and unpacked: ' + str(target))

if __name__ == '__main__':
    main()
