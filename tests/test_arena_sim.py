"""Tests for the Gen 9 arena simulator (scripts/arena_sim.py). Dependency-light: numpy and scipy only."""
import gzip
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import arena_sim as sim  # noqa: E402


class StoppingRules(unittest.TestCase):
    def test_hand_rule_matches_a_direct_t_interval(self):
        from scipy import stats
        rng = np.random.default_rng(1)
        X = (rng.normal(0.3, 3.0, size=(40, 3000))).astype(np.float32)
        d, b = sim.HandRule(first=1000, every=100, last=3000).run(X)
        for r in range(40):
            want_d, want_b = 0, 3000
            for t in range(1000, 3001, 100):
                x = X[r, :t].astype(np.float64)
                lo = x.mean() - stats.t.ppf(0.975, t - 1) * x.std(ddof=1) / math.sqrt(t)
                if lo > 0:
                    want_d, want_b = 1, t
                    break
            self.assertEqual((int(d[r]), int(b[r])), (want_d, want_b))

    def test_always_valid_rules_keep_false_promotion_at_or_under_the_level(self):
        rng = np.random.default_rng(2)
        X = rng.normal(0.0, 3.0, size=(400, 6000)).astype(np.float32)
        for rule in (sim.MixtureCS(futility=-99), sim.EmpiricalBernsteinCS(futility=-99)):
            d, _ = rule.run(X)
            # two-sided level 0.05 bounds the chance of ever crossing either side; one side gets about half
            self.assertLessEqual((d == 1).mean(), 0.05, rule.name)

    def test_always_valid_rules_promote_a_clear_lead(self):
        rng = np.random.default_rng(3)
        X = rng.normal(1.0, 3.0, size=(100, 4000)).astype(np.float32)
        for rule in (sim.MixtureCS(), sim.EmpiricalBernsteinCS()):
            d, b = rule.run(X)
            self.assertGreater((d == 1).mean(), 0.95, rule.name)
            self.assertLess(np.median(b), 2500, rule.name)

    def test_futility_stops_a_clear_loser(self):
        rng = np.random.default_rng(4)
        X = rng.normal(-0.5, 3.0, size=(100, 8000)).astype(np.float32)
        for rule in (sim.MixtureCS(), sim.EmpiricalBernsteinCS()):
            d, _ = rule.run(X)
            self.assertGreater((d == -1).mean(), 0.95, rule.name)
            self.assertEqual((d == 1).sum(), 0, rule.name)

    def test_mixture_radius_shrinks_with_boards(self):
        r = [float(sim.mixture_radius(t, 10.0, 0.05, sim.MixtureCS().rho2)) for t in (200, 2000, 20000)]
        self.assertGreater(r[0], r[1])
        self.assertGreater(r[1], r[2])

    def test_fixed_sample_size(self):
        # 80% power at one-sided 0.025: (1.96 + 0.8416)^2 (sigma / gap)^2
        n = sim.fixed_sample_size(0.8, 0.1, 3.2)
        self.assertAlmostEqual(n, (1.959964 + 0.841621) ** 2 * 32 ** 2, delta=1.0)
        self.assertIsNone(sim.fixed_sample_size(0.5, 0.0, 3.2))


class Noise(unittest.TestCase):
    def test_bootstrap_noise_is_centred_and_keeps_its_spread(self):
        values = np.array([-12, -6, 0, 0, 0, 0, 0, 0, 6, 12], np.float32)
        n = sim.Noise('t', values=values - values.mean())
        x = n.draw(np.random.default_rng(5), (200000,))
        self.assertAlmostEqual(float(x.mean()), 0.0, delta=0.05)
        self.assertAlmostEqual(float(x.std()), float(values.std()), delta=0.05)
        self.assertAlmostEqual(n.sigma, float(values.std()), places=4)
        self.assertAlmostEqual(sim.Noise('g', sd=2.0, scale=2.0).sigma, 4.0)


class Ratings(unittest.TestCase):
    def test_fit_recovers_strengths_from_exact_pair_means(self):
        truth = np.array([0.3, 0.0, -0.7, -1.7])
        P = 4
        n = np.zeros((P, P)); sums = np.zeros((P, P)); sq = np.zeros((P, P))
        for i in range(P):
            for j in range(i + 1, P):
                n[i, j] = 100
                d = truth[i] - truth[j]
                x = np.array([d - 1.0, d + 1.0] * 50)        # mean exactly d, variance 1
                sums[i, j] = x.sum(); sq[i, j] = (x * x).sum()
        s, _ = sim.fit_ratings(n, sums, sq, list(range(P)))
        np.testing.assert_allclose(s, truth - truth.mean(), atol=1e-4)

    def test_variance_allocation_spends_the_budget_and_finds_the_unmeasured_pair(self):
        spec = sim.ArenaSpec(players=3, boards_per_epoch=500, chunk=50)
        P = 3
        n = np.zeros((P, P)); sums = np.zeros((P, P)); sq = np.zeros((P, P))
        n[0, 1] = 5000; sums[0, 1] = 0.0; sq[0, 1] = 5000 * 9.0
        n[1, 2] = 5000; sums[1, 2] = 0.0; sq[1, 2] = 5000 * 9.0
        alloc = sim.allocate_variance(spec, [0, 1, 2], n, sums, sq, [(0, 1), (0, 2), (1, 2)])
        self.assertEqual(sum(alloc.values()), 500)
        self.assertGreater(alloc[(0, 2)], 0)

    def test_simulated_arena_error_falls_with_boards(self):
        pools = {'sibling': np.random.default_rng(6).normal(0, 3.3, 4000).astype(np.float32),
                 'unrelated': np.random.default_rng(7).normal(0, 4.2, 4000).astype(np.float32)}
        spec = sim.ArenaSpec(players=6, epochs=6, boards_per_epoch=1500, turnover_every=0)
        for schedule in ('equal', 'star', 'variance'):
            curves = np.array([sim.simulate_arena(spec, schedule, pools, np.random.default_rng([8, r])) for r in range(20)])
            m = curves.mean(axis=0)
            self.assertLess(m[-1], m[0], schedule)


class CountingRules(unittest.TestCase):
    def test_counted_rows_applies_the_dashboard_rules(self):
        base = dict(generation=7, cohort='c', ref='r', retired=False, allowed_pairs=None, index=0, native_ok=True)
        rows = [
            dict(base, source='a', snapshot_epoch=100, pair='7s-32~6-32', family='f1', completed_epoch=10, common=3, native=1),
            dict(base, source='b', snapshot_epoch=100, pair='7s-32~6-32', family='f1', completed_epoch=20, common=-6, native=0),
            dict(base, source='a', snapshot_epoch=100, pair='6-32~7s-32', family='f2', completed_epoch=11, common=2, native=2),
            dict(base, source='a', snapshot_epoch=100, pair='7s-32~6-32', family='f3', completed_epoch=200, common=5, native=5),
            dict(base, source='a', snapshot_epoch=100, pair='6-32~ben32', family='f4', completed_epoch=12, common=5, native=5),
        ]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'rows.jsonl.gz'
            with gzip.open(path, 'wt') as f:
                for r in rows:
                    f.write(json.dumps(r) + '\n')
            got = sim.counted_rows(path)
        self.assertEqual([(r['pair'], r['family'], r['common']) for r in got],
                         [('7s-32~6-32', 'f1', 3), ('7s-32~6-32', 'f2', -2)])


if __name__ == '__main__':
    unittest.main()
