#!/usr/bin/env python3
"""Validate inputs, partition the given reference, and prepare VGA LEF models."""
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'partition'))
import flow


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def openroad_sdc(text):
    """Translate Genus's explicit true argument; retain the cell collection."""
    return re.sub(r'(?m)^(\s*set_dont_use)[ \t]+true[ \t]+', r'\1 ', text)


def main():
    flow.libraries()
    if '--check' in sys.argv:
        print('Input paths and pin-compatible library pairs validated.')
        return
    run = Path(os.environ['RUN_DIR'])
    inputs = ('REFERENCE_NETLIST', 'SDC_FILE', 'TOP_LIBERTY', 'BOTTOM_LIBERTY',
              'FULL_TOP_LEF', 'BOTTOM_LEF', 'TECH_LEF')
    settings = ('TOP_AREA_SCALE', 'MAX_IMBALANCE', 'FLOORPLAN_UTILIZATION',
                'TARGET_UTILIZATION', 'GP_DENSITY', 'CAPACITY_BASIS',
                'TOP_GP_HEIGHT', 'TOP_DP_HEIGHT', 'VIRTUAL_ROW_HEIGHT',
                'ROUTING_GUARD_BAND_ROWS', 'DP_MAX_DISPLACEMENT',
                'ORIENTATION_PATTERN', 'SIGNAL_ROUTING_LAYERS', 'CLOCK_ROUTING_LAYERS')
    config = {k: {'path': os.environ[k], 'sha256': digest(os.environ[k])} for k in inputs}
    config.update({k: os.environ[k] for k in settings})
    manifest = run / 'inputs.json'
    if manifest.exists() and json.loads(manifest.read_text()) != config:
        raise SystemExit('Inputs/settings changed. Choose a new RUN_DIR.')
    manifest.write_text(json.dumps(config, indent=2) + '\n')
    partition = run / 'partition'
    partition.mkdir(exist_ok=True)
    os.environ['OUT'] = str(partition)
    reference = partition / 'cva6_bottom_reference.v'
    if not reference.exists():
        reference.symlink_to(Path(os.environ['REFERENCE_NETLIST']).resolve())
    marker = partition / 'partition.ok'
    if not marker.exists():
        if (partition / 'cva6_heterogeneous.v').exists():
            raise SystemExit('Incomplete partition exists. Choose a new RUN_DIR.')
        (partition / 'bottom_15nm.lib').write_text(
            flow.bottom_library_text(Path(os.environ['BOTTOM_LIBERTY'])))
        flow.partition()
        marker.write_text('Partition and tier-balance checks passed.\n')
    else:
        for name in ('cva6_heterogeneous.v', 'bottom_15nm.lib', 'tier_balance.json', 'partition.rpt'):
            if not (partition / name).is_file():
                raise SystemExit('Missing partition product: ' + name)
    (run / 'cva6.sdc').write_text(openroad_sdc(Path(os.environ['SDC_FILE']).read_text()))
    scripts = Path(os.environ['ROOT']) / 'python_scripts'
    lefs = run / 'initial/lef_test'
    lefs.mkdir(parents=True, exist_ok=True)
    for kind, height in [('gp', 'TOP_GP_HEIGHT'), ('dp', 'TOP_DP_HEIGHT')]:
        name = ('nangate_stdcell_top_tier_gp_macroheight_0p700_site_0p466.lef' if kind == 'gp'
                else 'nangate_stdcell_top_tier_dp_macroheight_0p466_site_0p466.lef')
        target = lefs / name
        if not target.exists():
            subprocess.run([sys.executable, str(scripts / 'make_dp_rowheight_lef.py'),
                            '--input-lef', os.environ['FULL_TOP_LEF'], '--output-lef', str(target),
                            '--target-height', os.environ[height],
                            '--site-height', os.environ['VIRTUAL_ROW_HEIGHT']], check=True)
    print('Prepared ' + str(run))
    print('Run ./flow/run.sh generate to create the initial/compact DEFs and placement Tcl files.')


if __name__ == '__main__':
    main()
