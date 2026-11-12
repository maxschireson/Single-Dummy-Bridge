"""Tests for bridge_harness/arena_ratings.py and the simulator's vectorised betting test. numpy only."""
import math
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'scripts'))
from bridge_harness import arena_ratings as ar  # noqa: E402
import arena_sim as sim  # noqa: E402


def exact_pairs(truth, names, n=400, g=None):
    out = []
    for a in range(len(names)):
        for b in range(a + 1, len(names)):
            d = truth[a] - truth[b] + (g.get((a, b), 0.0) if g else 0.0)
            out.append(ar.Pair(names[a], names[b], n, d, 9.0))
    return out


class Fit(unittest.TestCase):
    names = ['a', 'b', 'c', 'd', 'e', 'f']
    truth = np.array([0.0, 0.3, -0.7, -1.7, 0.1, 0.2])

    def test_recovers_strengths_from_the_reference(self):
        R = ar.fit(exact_pairs(self.truth, self.names), self.names, 'a')
        for k, p in enumerate(self.names):
            self.assertAlmostEqual(R.strength(p)[0], self.truth[k], delta=0.01)
        self.assertEqual(R.strength('a'), (0.0, 0.0))
        self.assertEqual(R.t2, 0.0)

    def test_a_pair_effect_raises_t2_and_the_cell_keeps_the_pair_own_result(self):
        pairs = exact_pairs(self.truth, self.names, n=2000, g={(2, 3): 1.0})
        R = ar.fit(pairs, self.names, 'a')
        self.assertGreater(R.t2, 0.0)
        est, var = R.cell('c', 'd')
        self.assertGreater(est, (self.truth[2] - self.truth[3]) + 0.7)      # mostly its own result
        est_rev, _ = R.cell('d', 'c')
        self.assertAlmostEqual(est_rev, -est, places=9)

    def test_unplayed_pair_is_the_model_prediction(self):
        pairs = [p for p in exact_pairs(self.truth, self.names) if (p.i, p.j) != ('b', 'c')]
        R = ar.fit(pairs, self.names, 'a')
        est, var = R.cell('b', 'c')
        self.assertAlmostEqual(est, self.truth[1] - self.truth[2], delta=0.02)
        self.assertEqual((est, var), R.predict('b', 'c'))

    def test_field_score_and_worst_cell(self):
        R = ar.fit(exact_pairs(self.truth, self.names), self.names, 'a')
        F, v, worst = R.field_score('b', {'c': 0.5, 'a': 0.5})
        self.assertAlmostEqual(F, 0.5 * (0.3 + 0.7) + 0.5 * 0.3, delta=0.02)
        self.assertGreater(v, 0)
        self.assertEqual(worst['opponent'], 'a')

    def test_gain_prefers_a_pair_that_touches_the_contrast(self):
        pairs = exact_pairs(self.truth, self.names, n=50)
        R = ar.fit(pairs, self.names, 'a')
        u = np.zeros(len(self.names)); u[1], u[2] = 1, -1
        self.assertGreater(R.gain('b', 'c', u), R.gain('d', 'e', u))

    def test_summarise_folds_both_orientations(self):
        out = ar.summarise([('x', 'y', 3), ('y', 'x', 1), ('x', 'y', 5)])
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0].i, out[0].j, out[0].n), ('x', 'y', 3))
        self.assertAlmostEqual(out[0].mean, (3 - 1 + 5) / 3)


class Betting(unittest.TestCase):
    def test_scalar_and_vectorised_tests_agree(self):
        rng = np.random.default_rng(3)
        X = np.where(rng.random((30, 3000)) < 0.7, 0, rng.integers(-12, 13, (30, 3000))).astype(np.float32) + 0.4
        P, F = sim.betting_first_crossings(X, ds=(0.05,))
        dec, when = sim.outcome(P, F[0.05], 3000)
        for r in range(30):
            t = ar.BettingTest(cap=3000)
            for x in X[r]:
                res = t.update(float(x))
                if res:
                    break
            want = {'promote': 1, 'futility': -1, 'cap': 0}[res]
            self.assertEqual((int(dec[r]), int(when[r])), (want, t.t), r)

    def test_false_promotion_at_most_alpha_on_a_null_heavy_tailed_stream(self):
        rng = np.random.default_rng(4)
        X = np.where(rng.random((600, 4000)) < 0.75, 0, rng.choice([-13, -6, -2, 2, 6, 13], (600, 4000))).astype(np.float32)
        P, _ = sim.betting_first_crossings(X, ds=(0.05,))
        self.assertLessEqual((P > 0).mean(), 0.05)

    def test_outcome_orders_the_bounds_and_respects_the_cap(self):
        dec, when = sim.outcome(np.array([10, 0, 50, 0, 30]), np.array([20, 15, 40, 0, 30]), 35)
        self.assertEqual(dec.tolist(), [1, -1, 0, 0, 1])
        self.assertEqual(when.tolist(), [10, 15, 35, 35, 30])

    def test_display_radius_is_the_asymptotic_sequence(self):
        r2 = 7.94 / 1500
        t, sd = 1500, 3.0
        want = sd * math.sqrt(2 * (t * r2 + 1) / (t * t * r2) * math.log(math.sqrt(t * r2 + 1) / 0.05))
        self.assertAlmostEqual(ar.display_radius(t, sd), want)


if __name__ == '__main__':
    unittest.main()
