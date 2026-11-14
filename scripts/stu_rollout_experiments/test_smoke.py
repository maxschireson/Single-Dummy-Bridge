"""Run with STU_RUNTIME pointing at the pinned research checkout."""
import os
from pathlib import Path
import random
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

runtime = Path(os.environ['STU_RUNTIME'])
sys.path[:0] = [str(runtime), str(runtime / 'tests')]
import numpy as np
from bridge_harness.players import Decision
from bridge_harness.gen6 import View
from bridge_harness.gen7 import hidden_plays
from bridge_harness.plan_rollout import Rows
from bridge_harness import x8_player as xp
from engine import ExperimentalPlayer, ReplanningSeats, row_view, view_seed
from test_x8 import Fixture8, spot
from test_gen7 import played
from test_gen6 import FakeBelief, FakeState


class SmokeTests(Fixture8):
    def test_real_inner_player_runs_flat_and_factory_is_restored(self):
        settings = dict(stages=[dict(from_trick=1, to_trick=13, mode='rollout', layouts=4, first=4, cards=2)],
                        lead=dict(mode='rollout', layouts=4, first=4, cards=2), capture=dict(level=0, forks=0))
        p = self.make8(settings, cls=ExperimentalPlayer)
        p.experiment.update(recursive='uniform', inner_layouts=2, max_calls=1, window_plies=8)
        before = xp.Seats
        for seed in range(5):
            _, o, _ = spot(seed, 32)
            with patch('bridge_harness.gen6.BidderState', FakeState), patch('bridge_harness.mixed_arena.Weights', FakeBelief):
                result = p.choose(o, random.Random(seed))
            self.assertIn(result.card, o.legal)
            self.assertIs(xp.Seats, before)
            if p.recursive_stats['calls']:
                self.assertFalse(p.child.experiment.get('recursive'))
                break
        self.assertGreater(p.recursive_stats['calls'], 0)

    def test_row_view_equals_game_and_ignores_hidden_allocation(self):
        for seed in range(8):
            _, game, _ = played(seed, 12)
            o = game.observation()
            world = tuple(tuple(sorted(h)) for h in game.hands)
            rows = Rows(o, [world])
            for _ in range(12):
                self.assertEqual(row_view(rows, 0), game.observation())
                masked = row_view(rows, 0)
                hidden = [s for s in range(4) if masked.known_hands[s] is None]
                a, b = (int(np.flatnonzero(rows.holder[0] == s)[0]) for s in hidden)
                altered = rows.copy()
                altered.holder[0, a], altered.holder[0, b] = altered.holder[0, b], altered.holder[0, a]
                self.assertEqual(row_view(altered, 0), masked)
                self.assertEqual(view_seed(row_view(altered, 0)), view_seed(masked))
                card = game.observation().legal[0]
                game.play(card)
                rows.play([card])

    def test_reader_routes_plain_and_pooled_by_controller_and_restores(self):
        exercised = set()
        for pooled in (False, True):
            p = self.make8(dict(blind=True, names={'self': 'me', '*': '', 'they_see': ''},
                                mix=dict(read_declarer=['*'], read_defender=['*']) if pooled else {}), cls=ExperimentalPlayer)
            p.experiment['reader_identity'] = True
            p.net.vocab = {'?': 0, 'me': 1}
            p.meet('hidden-opponent')
            for seed in range(12):
                _, o, _ = spot(seed, 20)
                view = View(o)
                assign = view.uniform(4, np.random.default_rng(seed))
                for play in hidden_plays(o, True):
                    p.play_cache, p.mix_cache = (None, {}), (None, {})
                    called = []
                    def score(batch):
                        called.append(p.net.who)
                        return np.where(batch['legal'], -np.log(batch['legal'].sum(axis=1))[:, None], -100.)
                    with patch.object(p.net, 'log_policy_arrays', side_effect=score):
                        p.play_log_probabilities(o, view, assign, [play])
                    mine = play[2] % 2 == o.controller % 2
                    if called:
                        exercised.add((pooled, mine))
                        self.assertTrue(all(w == (('me', '') if mine else ('', '')) for w in called))
                    self.assertEqual(p.net.who, ('me', ''))
        self.assertEqual(exercised, {(p, m) for p in (False, True) for m in (False, True)})

    def test_recursive_calls_are_bounded_and_only_receive_observations(self):
        p = self.make8(cls=ExperimentalPlayer)
        p.experiment.update(recursive='uniform', max_calls=2, window_plies=8)
        p.recursive_stats = dict(opportunities=0, calls=0, cache_hits=0, changed=0, net_rows=0)
        p.recursive_cache = {}
        seen = []
        def choose(o, rng):
            self.assertEqual(sum(h is not None for h in o.known_hands), 2)
            self.assertIs(xp.Seats, __import__('bridge_harness.x8_rollout', fromlist=['Seats']).Seats)
            seen.append(o)
            return Decision(o.legal[-1], {})
        with patch.object(p, 'child_player', return_value=SimpleNamespace(choose=choose)):
            _, o, world = spot(4, 20)
            rows = Rows(o, [world] * 8)
            rows.play([o.legal[0]] * 8)
            seats = ReplanningSeats([p.net], 'top', owner=p).start(o)
            for _ in range(8):
                cards, _, _ = seats.cards(rows)
                rows.play(cards)
        self.assertGreater(len(seen), 0)
        self.assertLessEqual(len(seen), 2)


if __name__ == '__main__':
    unittest.main()
