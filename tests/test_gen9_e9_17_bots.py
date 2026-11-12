"""E9-17's bots file is what its script writes, and the reader's rule tables are well formed."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class E917Bots(unittest.TestCase):
    def test_the_file_is_generated_and_reads_each_rule(self):
        subprocess.run([sys.executable, str(ROOT / 'scripts' / 'gen9_e9_17_bots.py'), '--check'], check=True)
        from bridge_harness.signals import SignalModel
        bots = json.loads((ROOT / 'configs' / 'gen9-e9-17-bots.json').read_text())
        r, x = bots['r9t-32'], bots['8x-32']
        self.assertEqual(r['gen7'], x['gen7'])                              # r9t-32 is 8x-32 plus the reader
        for t, place in (('t-high', 1), ('t-low', 0)):
            block = r['gen9']['models'][t]['carding']
            self.assertEqual(block['phi'], x['gen7']['opponent_play_weight'][t])
            model = SignalModel(block['descriptor'], emission=block['emission'])
            for table in model.emission.values():
                self.assertTrue((table[:, place] == 1).all())               # the same place in the class for every message


if __name__ == '__main__':
    unittest.main()
