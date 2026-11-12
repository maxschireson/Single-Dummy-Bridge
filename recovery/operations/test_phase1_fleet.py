"""Operational invariants for shared phase-1 limits, independent of scores."""
import unittest
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
from phase1_fleet import update
from phase1_fleet import canonical_pair, count_families, PAIRS


class FleetTests(unittest.TestCase):
    def test_mirrored_feeds_and_unpublished_local_receipts_do_not_double_count(self):
        first = [dict(pair='7s-32~6-32', family=str(i), imps=10) for i in range(2000)]
        mirror = [dict(pair='6-32~7s-32', family=str(i), imps=-10) for i in range(2000)]
        local = [dict(pair='7s-32~6-32', family='1999', imps=0)]
        seen = count_families(first + mirror + local)
        self.assertEqual(len(seen['7s-32~6-32']), 2000)
        self.assertFalse(all(len(v) >= 2000 for v in seen.values()))

    def test_only_authorized_pairs_can_satisfy_phase1(self):
        rows = [dict(pair=p, family=str(i)) for p in PAIRS for i in range(2000)]
        rows += [dict(pair='7f-32~7f-32', family='not-phase1'), dict(pair='7s-32~7s-32', family='not-phase1')]
        self.assertTrue(all(len(v) == 2000 for v in count_families(rows).values()))
        self.assertIsNone(canonical_pair('7s-32~7s-32'))
        self.assertIsNone(canonical_pair('7s-32~unknown'))

    def test_drain_only_after_all_owned_pooled_pairs_reach_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp); (run / 'receipts').mkdir()
            owned = ['7s-32~6-32', '7s-32~5RZ32', '7s-32~1']
            manifest = dict(identity='cohort', bots={'7s-32': {'identity': 'actor'}},
                            phase1=dict(owned_pairs=owned))
            (run / 'manifest.json').write_text(json.dumps(manifest))
            families = {p: [str(i) for i in range(2000 if p in owned else 0)] for p in PAIRS}
            families[owned[-1]].pop()
            (run / 'phase1-seen-families.json').write_text(json.dumps(dict(actor_identity='actor', families=families)))
            with patch('phase1_fleet.subprocess.check_output', return_value=''):
                self.assertFalse(update(run, run)['owned_complete'])
                self.assertFalse((run / 'STOP').exists())
                (run / 'receipts' / '000001.json').write_text(json.dumps(dict(
                    manifest_identity='cohort', pair=owned[-1], family='1999')))
                result = update(run, run)
            self.assertTrue(result['owned_complete'])
            self.assertFalse(result['all_five_complete'])
            self.assertFalse(result['phase2_authorized'])
            self.assertIn('drain', (run / 'STOP').read_text())


if __name__ == '__main__':
    unittest.main()
