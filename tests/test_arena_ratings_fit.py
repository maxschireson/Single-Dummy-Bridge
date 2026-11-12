"""Tests for scripts/arena_ratings_fit.py (G9-D3). numpy only; no network."""
from pathlib import Path
import random
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'scripts'))
import arena_ratings_fit as fit  # noqa: E402


def row(pair, family, t, common, native, source='s1', snapshot=1e9, cohort='c', allowed=None):
    return dict(source=source, generation=7, cohort=cohort, ref='r', retired=False, allowed_pairs=allowed, snapshot_epoch=snapshot,
                pair=pair, index=0, family=family, completed_epoch=t, common=common, native=native, native_ok=True)


class Tables(unittest.TestCase):
    bidders = {'s1': dict(bot='6-32', sha256='5b7ea255' + '0' * 56), 's5': dict(bot='5', sha256='9ee52f3b' + '0' * 56)}

    def test_conditions_are_split_by_common_bidder_and_the_dashboard_rules_apply(self):
        rows = [row('7s-32~6-32', 'f1', 1, 3, 3), row('6-32~7s-32', 'f1', 2, -6, -6),     # same family, later: dropped
                row('6-32~7s-32', 'f2', 3, 2, 1),                                          # flipped to 7s-32's side
                row('7s-32~6-32', 'f3', 4, 5, 5, snapshot=3),                              # after the snapshot
                row('6-32~ben32', 'f4', 5, 5, 5),                                          # hidden actor
                row('7s-32~7s-32', 'f5', 6, None, None),                                   # self-play
                row('5~ben', 'f6', 7, -2, -1, source='s5'), row('71s-32~7s-32', 'f7', 8, 1, 2)]
        t = fit.tables(rows, self.bidders)
        self.assertEqual(sorted(t), ['common@5b7ea255', 'common@9ee52f3b', 'native'])
        self.assertEqual(t['common@5b7ea255'], [('7s-32', '6-32', 3), ('7s-32', '6-32', -2), ('71s-32', '7s-32', 1)])
        self.assertEqual(t['common@9ee52f3b'], [('5', 'ben', -2)])
        self.assertEqual(len(t['native']), 4)

    def test_a_bot_the_dashboard_order_does_not_list_comes_first(self):
        self.assertEqual(fit.normalize('7s-32~71s-32'), ('71s-32~7s-32', True))
        self.assertEqual(fit.normalize('71s-32~7s-32'), ('71s-32~7s-32', False))


class Fit(unittest.TestCase):
    def results(self, truth, pairs, n=400, seed=1, effect=None):
        rng = random.Random(seed)
        out = []
        for a, b in pairs:
            d = truth[a] - truth[b] + (effect or {}).get((a, b), 0.0)
            out += [(a, b, d + rng.choice((-3.0, 0.0, 0.0, 3.0))) for _ in range(n)]
        return out

    truth = {'ben': 0.0, '6-32': -0.1, '7s-32': 0.2, '5RZ32': -0.8, '1': -1.8, '2': -0.9}
    cyc = [('7s-32', '6-32'), ('6-32', 'ben'), ('7s-32', 'ben'), ('6-32', '5RZ32'), ('7s-32', '5RZ32'), ('6-32', '1'), ('7s-32', '1'), ('6-32', '2')]

    def test_reproduces_and_marks_the_only_link_untestable(self):
        t = fit.fit_table(self.results(self.truth, self.cyc))
        rows = {r['pair']: r for r in t['pairs']}
        self.assertTrue(all(r['fitted_in_ci'] for r in rows.values()))
        self.assertFalse(rows['6-32~2']['testable'])              # player 2 meets only 6-32
        self.assertIsNone(rows['6-32~2']['p_holm'])
        self.assertTrue(rows['7s-32~6-32']['testable'])
        self.assertFalse(any(r['out_of_line'] for r in rows.values() if r['testable']))
        self.assertAlmostEqual(t['players']['7s-32']['strength'], 0.2, delta=0.12)

    def test_a_large_pair_effect_is_flagged(self):
        t = fit.fit_table(self.results(self.truth, self.cyc, n=3000, effect={('7s-32', '5RZ32'): 1.0}))
        rows = {r['pair']: r for r in t['pairs']}
        self.assertTrue(rows['7s-32~5RZ32']['out_of_line'])

    def test_holm(self):
        self.assertEqual(fit.holm([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06])


if __name__ == '__main__':
    unittest.main()
