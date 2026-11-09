import json
import os
import random
import tempfile
import unittest
from unittest.mock import patch

from bridge_harness.core import Game
from bridge_harness.corpus import generate
from bridge_harness.players import PIMCPlayer
from bridge_harness.multiscore import MultiScorePlayer, make_multiscore_player

COST = {'dds_calls', 'dds_native_solves', 'dds_cache_hits', 'dds_duplicate_worlds',
        'dds_nodes', 'work_accounting', 'scored_budget', 'multi_score'}


def semantic(d):
    return d.card, {k: v for k, v in d.details.items() if k not in COST}


def positions():
    game = Game(next(generate(1, seed=871)))
    rng = random.Random(19)
    for ply in range(52):
        if ply in (0, 19, 28, 29, 30, 31, 40, 48, 51):
            yield game.observation()
        game.play(rng.choice(game.observation().legal))


class MultiScoreTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'BRIDGE_DDS_CACHE': ''})
        self.env.start(); self.addCleanup(self.env.stop)

    def test_prefix_choices_values_and_rng_match_standalone(self):
        for objective in ('score', 'tricks', 'make'):
            base = PIMCPlayer(64, objective, near_tie=.125)
            multi = MultiScorePlayer(base, active_samples=64)
            self.addCleanup(multi.close)
            for o in positions():
                rng = random.Random(817)
                with patch.object(base.dds, 'solve_batch', wraps=base.dds.solve_batch) as batch:
                    result = multi.choose_all(o, rng)
                    self.assertEqual(batch.call_count, int(len(o.legal) > 1))
                for budget in (16, 32, 64):
                    solo = PIMCPlayer(budget, objective, near_tie=.125)
                    try:
                        sr = random.Random(817); expected = solo.choose(o, sr)
                        self.assertEqual(semantic(result.decisions[budget]), semantic(expected))
                        self.assertEqual(result.rng_states[budget], sr.getstate())
                    finally:
                        solo.close()
                self.assertEqual(rng.getstate(), result.rng_states[64])
                self.assertEqual(base.samples, 64)

    def test_active_budget_and_work_logged_once_with_warm_cache(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'BRIDGE_DDS_CACHE': tmp+'/cache.sqlite'}):
            multi = MultiScorePlayer(PIMCPlayer(32, 'tricks'), active_samples=16)
            self.addCleanup(multi.close)
            o = next(positions())
            first = multi.choose(o, random.Random(3))
            second = multi.choose(o, random.Random(3))
            self.assertEqual(semantic(first), semantic(second))
            self.assertEqual(second.details['dds_native_solves'], 0)
            self.assertEqual(second.details['dds_cache_hits'], 64)
            self.assertEqual(second.details['dds_calls'], 64)
            self.assertEqual(second.details['samples'], 16)
            self.assertTrue(all(d['details']['dds_calls'] == 0 for d in second.details['multi_score']['decisions'].values()))
            json.dumps(second.details)

    def test_each_active_budget_advances_its_own_rng(self):
        o = list(positions())[-3]
        for n in (16, 32, 64):
            multi = MultiScorePlayer(PIMCPlayer(32, 'tricks'), active_samples=n)
            solo = PIMCPlayer(n, 'tricks')
            try:
                a, b = random.Random(711), random.Random(711)
                actual = multi.choose(o, a); expected = solo.choose(o, b)
                self.assertEqual(semantic(actual), semantic(expected))
                self.assertEqual(a.getstate(), b.getstate())
            finally:
                multi.close(); solo.close()

    def test_invalid_settings(self):
        base = PIMCPlayer(32); self.addCleanup(base.close)
        for budgets, active in [([], 64), ([32,16,64],64), ([16,16,64],64), ([16,32,64],8), ([16.,32,64],64)]:
            with self.assertRaises(ValueError): MultiScorePlayer(base, budgets, active)
        with self.assertRaises(ValueError): make_multiscore_player(exploration=-1)


if __name__ == '__main__': unittest.main()
