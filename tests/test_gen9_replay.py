"""Gen 9 replay reader in the player shell (G9-B7): the real reader behind gen9.py's replay_reader hook."""
from pathlib import Path
import unittest

import numpy as np

from bridge_harness.gen6 import View
from bridge_harness.gen6_nets import hand_types
from test_gen9_player import EARLY, Shell

ROOT = Path(__file__).resolve().parents[1]
GEN6 = ROOT / 'models/bidding/gen6-candidate-2026-11-11/bidder.keras'

try:
    import h5py  # noqa: F401
    HAVE = GEN6.exists()
except ImportError:
    HAVE = False


@unittest.skipUnless(HAVE, 'needs h5py and the restored Gen 6 bidder (python models/bidding/gen6-candidate-2026-11-11/restore_model.py)')
class RealReplayTests(Shell):
    def test_correction_is_replay_minus_scorer_for_a_house_profile(self):
        from bridge_harness.cards.replay import ReplayReader
        model = dict(kind='house', profiles={'house-gen6': 1.})
        p = self.make9(gen7=EARLY, gen9=dict(models={'them': model}, replay_reader='bridge_harness.cards.replay:replay_factory'))
        p.meet('them')
        rr = ReplayReader(str(GEN6))
        checked = 0
        for o, game in self.two_hidden(range(30), (5, 9), declarer=True):
            view = View(o)
            assign = view.uniform(48, np.random.default_rng(4))
            change = p.replay_correction(o, view, assign)
            self.assertIsNotNone(change)
            want = 0.
            for j, seat in enumerate(view.hidden):
                ln, hn = hand_types(view.original(assign, j))
                want = want + rr.type_log_score(ln, hn, seat, o.dealer, o.vulnerability, o.auction) \
                    - p.scorer.type_log_score(ln, hn, seat, o.dealer, o.vulnerability, o.auction)
            np.testing.assert_allclose(change, want, atol=1e-9)
            checked += 1
        self.assertGreater(checked, 3)

    def test_profiles_without_a_held_bidder_change_nothing(self):
        model = dict(kind='outside', profiles={'some-other-system': 1.})
        p = self.make9(gen7=EARLY, gen9=dict(models={'them': model}, replay_reader='bridge_harness.cards.replay:replay_factory'))
        p.meet('them')
        o, game = next(self.two_hidden(range(30), (5,), declarer=True))
        view = View(o)
        change = p.replay_correction(o, view, view.uniform(16, np.random.default_rng(0)))
        self.assertTrue(change is None or not np.any(change))


if __name__ == '__main__':
    unittest.main()
