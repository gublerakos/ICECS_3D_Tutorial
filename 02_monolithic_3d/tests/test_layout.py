#!/usr/bin/env python3
"""Static wiring checks for the prepared run directories (no OpenROAD needed)."""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'flow' / 'run.sh'
VARIANTS = subprocess.run([str(RUN), 'list'], check=True, stdout=subprocess.PIPE,
                          universal_newlines=True).stdout.split()
VARS = {'data_path': './data', 'scripts_path': './tcl_scripts', 'python_scripts': './python_scripts'}
# Stale reference in the original data, only reached by the standalone build_bank.sh,
# which build_3DIC.sh does not call.
KNOWN_STALE = ('nangate_stdcell_bottom_tie_shrinkedr.lef',)
REFERENCE = re.compile(
    r'(\.\./do_(?:synth|genram)/[^\s"\\}\]\[;]+|\./(?:data|tcl_scripts|python_scripts)/[^\s"\\}\]\[;]+'
    r'|\$(?:data_path|scripts_path|python_scripts)/[^\s"\\}\]\[;]+)')

def prepare(variant, run_dir):
    env = dict(os.environ, RUN_DIR=str(run_dir))
    subprocess.run([str(RUN), 'prepare', variant], check=True, env=env, stdout=subprocess.PIPE)
    return Path(run_dir) / 'work'


class LayoutTest(unittest.TestCase):
    def test_every_referenced_input_resolves(self):
        for variant in VARIANTS:
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as tmp:
                work = prepare(variant, Path(tmp) / variant)
                checked = 0
                for path in sorted(work.rglob('*')):
                    if path.suffix not in ('.tcl', '.vars', '.sh') or not path.is_file():
                        continue
                    for line in path.read_text().splitlines():
                        if line.lstrip().startswith('#'):
                            continue
                        for ref in REFERENCE.findall(line):
                            for name, value in VARS.items():
                                ref = ref.replace('$' + name, value)
                            if ref.endswith(KNOWN_STALE):
                                continue
                            self.assertTrue((work / ref).exists(), '%s: %s' % (path.name, ref))
                            checked += 1
                self.assertGreater(checked, 0)

    def test_scripts_are_well_formed(self):
        for script in sorted((ROOT / 'flow').rglob('*.sh')):
            subprocess.run(['bash', '-n', str(script)], check=True)

    @unittest.skipUnless(shutil.which('python3.12'), 'the flow scripts target python3.12')
    def test_python_scripts_compile(self):
        for script in sorted((ROOT / 'python_scripts').rglob('*.py')):
            subprocess.run(['python3.12', '-c', 'import ast,sys; ast.parse(open(sys.argv[1]).read())', str(script)],
                           check=True)


if __name__ == '__main__':
    unittest.main()
