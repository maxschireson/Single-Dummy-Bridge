"""Fork continuations batched with the main rollout rows (x8_rollout.FORK_BATCH) leave the main rows' play unchanged.

Mode 1 (batched) against mode 2 (each copy group finished after the main loop, from the same fork stream): the main
rows' tricks, claim floors, ends and lines are identical, and so are the forks taken. With seats that play their top
card the fork results are identical too; with drawing seats they come from the same stream in another order.
"""
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_harness import x8_rollout  # noqa: E402
from bridge_harness.x8_rollout import Seats, evaluate  # noqa: E402
from test_x8 import Fixture8, shuffled, spot  # noqa: E402


class ForkBatchTests(Fixture8):
    def run_both(self, mode, seed):
        p = self.make()
        _, o, world = spot(seed, 6 + 4 * (seed % 4))
        rng = random.Random(seed)
        worlds = [world] + [shuffled(o, world, rng) for _ in range(5)]
        cards = list(o.legal)[:3]
        out = []
        for fork_mode in (2, 1):
            with patch.object(x8_rollout, 'FORK_MODE', fork_mode), patch.object(x8_rollout, 'FORK_BATCH', fork_mode == 1):
                seats = Seats([p.net], mode, seed=seed).start(o)
                got = evaluate(o, worlds, cards, seats, forks=8, rng=np.random.default_rng(seed))
            out.append(got)
        return out

    def check(self, mode):
        forks = 0
        for seed in range(6):
            a, b = self.run_both(mode, seed)
            for k in ('tricks', 'floor', 'ended', 'lines'):
                self.assertTrue(np.array_equal(getattr(a, k), getattr(b, k)), (mode, seed, k))
            key = lambda f: (f.layout, f.first, f.prefix, f.seat, f.main, f.other)
            self.assertEqual([key(f) for f in a.forks], [key(f) for f in b.forks])
            if mode == 'top':
                self.assertEqual([(f.main_tricks, f.other_tricks) for f in a.forks],
                                 [(f.main_tricks, f.other_tricks) for f in b.forks])
            forks += len(a.forks)
        self.assertGreater(forks, 10)

    def test_top_card_seats(self):
        self.check('top')

    def test_drawing_seats(self):
        self.check('draw')


if __name__ == '__main__':
    unittest.main()
