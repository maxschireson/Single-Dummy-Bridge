"""Operational invariants for shared phase-1 limits, independent of scores."""
import unittest
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


if __name__ == '__main__':
    unittest.main()
