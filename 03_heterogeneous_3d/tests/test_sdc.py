import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'flow'))
from prepare import openroad_sdc

class SdcCompatibility(unittest.TestCase):
    def test_real_constraints_preserved(self):
        original=(Path(__file__).resolve().parents[1]/'data/cva6.sdc').read_text()
        converted=openroad_sdc(original)
        differences=[(a,b) for a,b in zip(original.splitlines(),converted.splitlines()) if a!=b]
        self.assertEqual(len(differences),5)
        self.assertTrue(all(b==a.replace('set_dont_use true ', 'set_dont_use ',1) for a,b in differences))
        self.assertEqual(len(original.splitlines()),len(converted.splitlines()))
        self.assertEqual(openroad_sdc(converted),converted)

if __name__ == '__main__':
    unittest.main()
