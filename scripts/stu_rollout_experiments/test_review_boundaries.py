"""Independent B review of prototype 7c79acf (issue #39).

STU_RUNTIME=/pinned/runtime OPENBLAS_NUM_THREADS=1 python FILE -v
Adapted by coordinator after fixes: original B01/B02 assertions retained;
expected-failure markers removed and the first-rejection witness now requires
a later uncertain node to remain eligible. Original evidence stays in PR #43.
No trained model or evaluation/training episode is consumed.
"""
import os
from dataclasses import replace
from pathlib import Path
import random
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

runtime = Path(os.environ['STU_RUNTIME']).resolve()
experiment_source = Path(os.environ.get('STU_EXPERIMENT_SOURCE', Path(__file__).parent)).resolve()
sys.path[:0] = [str(experiment_source), str(runtime), str(runtime / 'tests'), str(runtime / 'scripts')]
import numpy as np
from bridge_harness.core import Game
from bridge_harness.gen6 import View
from bridge_harness.plan_rollout import Rows
from bridge_harness.players import Decision
from bridge_harness import x8_player as xp
from bridge_harness.x8_rollout import Seats
from engine import ExperimentalPlayer, ReplanningSeats, row_view, view_seed
from test_x8 import Fixture8, spot
from test_gen6 import FakeBelief, FakeState
from test_gen7 import played


def policy(rows, other=None):
    legal = rows.legal()
    free = np.flatnonzero(legal.sum(axis=1) > 1)
    # A deterministic stub isolates scheduling from neural noise; legal only.
    logp = np.where(legal[free], 0., -np.inf)
    return legal.argmax(axis=1), free, logp


def owner(**settings):
    return SimpleNamespace(experiment=dict(recursive='uniform', max_calls=4,
                                         window_plies=8, **settings),
        recursive_stats=dict(opportunities=0, calls=0, cache_hits=0, changed=0, net_rows=0),
        recursive_cache={}, child_player=lambda: SimpleNamespace(
            choose=lambda o, rng: Decision(o.legal[-1], {})))


def seats_for(rows, p):
    seats = object.__new__(ReplanningSeats)
    seats.owner, seats.side, seats.seen_paths = p, rows.o.controller % 2, set()
    return seats


def eligible_batch():
    """Real legal rows with several distinct eligible child observations."""
    for seed in range(40):
        _, o, _ = spot(seed, 20)
        if o.controller % 2 == o.contract.declarer % 2:
            continue  # a defending partner sees a different hand across worlds
        view = View(o)
        worlds = [view.world(a) for a in view.uniform(16, np.random.default_rng(seed))]
        rows = Rows(o, worlds)
        rows.play([o.legal[0]] * rows.n)
        for _ in range(7):
            at = [i for i in range(rows.n) if rows.controller()[i] % 2 == o.controller % 2
                  and rows.legal()[i].sum() > 1]
            keys = {view_seed(row_view(rows, i)) for i in at}
            if len(keys) > 1:
                return rows.take(np.array(at))
            rows.play(policy(rows)[0])
    raise AssertionError('No multi-observation fixture')


class SchedulerReview(unittest.TestCase):
    def test_cached_card_is_independent_of_other_uncached_rows_at_budget_limit(self):
        rows = eligible_batch()
        keys = [view_seed(row_view(rows, i)) for i in range(rows.n)]
        low, high = int(np.argmin(keys)), int(np.argmax(keys))
        pair = rows.take(np.array([low, high]))
        p = owner()
        p.recursive_stats['calls'] = p.experiment['max_calls']
        wanted = row_view(pair, 1).legal[-1]
        p.recursive_cache[keys[high]] = wanted
        with patch.object(Seats, 'cards', side_effect=policy):
            alone = seats_for(pair, p).cards(pair.take(np.array([1])))[0][0]
            together = seats_for(pair, p).cards(pair)[0][1]
        self.assertEqual(alone, wanted)
        self.assertEqual(together, wanted,
            'An earlier uncached hash breaks the loop before an already cached card')

    def test_equal_observations_with_different_hidden_path_marks_use_same_cached_card(self):
        rows = eligible_batch().take(np.array([0, 0]))
        o = row_view(rows, 0)
        hidden = [s for s, h in enumerate(o.known_hands) if h is None]
        a, b = next((int(a), int(b))
                    for a in np.flatnonzero(rows.holder[1] == hidden[0])
                    for b in np.flatnonzero(rows.holder[1] == hidden[1]) if a // 13 == b // 13)
        rows.holder[1, a], rows.holder[1, b] = rows.holder[1, b], rows.holder[1, a]
        self.assertEqual(row_view(rows, 0), row_view(rows, 1))
        p = owner()
        p.recursive_cache[view_seed(o)] = o.legal[-1]
        seats = seats_for(rows, p)
        original = np.where(rows.holder[0] >= 0, rows.holder[0], rows.by[0])
        root_card = int(np.flatnonzero(rows.order[0] == len(rows.o.history) + 1)[0])
        seats.seen_paths.add((original.tobytes(), root_card))
        with patch.object(Seats, 'cards', side_effect=policy):
            chosen = seats.cards(rows)[0]
        self.assertEqual(chosen[0], chosen[1],
            'Hidden-world path eligibility precedes the observation cache')

    def test_first_rejected_selective_opportunity_leaves_later_nodes_eligible(self):
        rows = eligible_batch().take(np.array([0]))
        p = owner()
        p.experiment.update(recursive='selective', logp_margin=1.)
        seats = seats_for(rows, p)
        def confident(r, other=None):
            out, free, lp = policy(r)
            for k, i in enumerate(free):
                lp[k, out[i]] = 3.
            return out, free, lp
        with patch.object(Seats, 'cards', side_effect=confident):
            seats.cards(rows)
        self.assertEqual(p.recursive_stats['calls'], 0)
        self.assertEqual(len(seats.seen_paths), 0)
        rows.play(policy(rows)[0])
        while not rows.done and rows.played - len(rows.o.history) <= 8:
            with patch.object(Seats, 'cards', side_effect=policy):
                chosen = seats.cards(rows)[0]
            rows.play(chosen)
        self.assertGreater(p.recursive_stats['calls'], 0)

    def test_child_exception_restores_factory(self):
        rows = eligible_batch().take(np.array([0]))
        p = owner()
        def fail(o, rng):
            self.assertIs(xp.Seats, Seats)
            raise RuntimeError('child sentinel')
        p.child_player = lambda: SimpleNamespace(choose=fail)
        sentinel = object()
        with patch.object(xp, 'Seats', sentinel), patch.object(Seats, 'cards', side_effect=policy):
            with self.assertRaisesRegex(RuntimeError, 'child sentinel'):
                seats_for(rows, p).cards(rows)
            self.assertIs(xp.Seats, sentinel)

    def test_row_view_exact_all_seats_and_dummy_after_opening_lead(self):
        coverage = set()
        for seed in range(12):
            board, _, _ = played(seed, 0)
            rot = seed % 4
            board = replace(board, hands=tuple(board.hands[(s - rot) % 4] for s in range(4)),
                            dealer=(board.dealer + rot) % 4,
                            contract=replace(board.contract, declarer=(board.contract.declarer + rot) % 4))
            game = Game(board)
            o = game.observation()
            rows = Rows(o, [tuple(tuple(sorted(h)) for h in game.hands)])
            # row_view is for post-root continuation, not the unseen-dummy root.
            card = o.legal[0]
            game.play(card)
            rows.play([card])
            while not game.done:
                o = game.observation()
                self.assertEqual(row_view(rows, 0), o)
                coverage.add((o.controller, o.actor == o.contract.dummy))
                view = View(o)
                # View reconstructs the same public void constraints from history.
                self.assertEqual(View(row_view(rows, 0)).voids, view.voids)
                card = o.legal[0]
                game.play(card)
                rows.play([card])
        self.assertEqual({s for s, _ in coverage}, set(range(4)))
        self.assertTrue(any(dummy for _, dummy in coverage))


class PlayerReview(Fixture8):
    def settings(self):
        return dict(stages=[dict(from_trick=1, to_trick=13, mode='rollout',
                                layouts=4, first=4, cards=2)],
                    lead=dict(mode='rollout', layouts=4, first=4, cards=2),
                    capture=dict(level=0, forks=0))

    def test_null_and_zero_budget_match_base_actions_values_and_rng(self):
        base = self.make8(self.settings())
        null = self.make8(self.settings(), cls=ExperimentalPlayer)
        zero = self.make8(self.settings(), cls=ExperimentalPlayer)
        zero.experiment.update(recursive='uniform', max_calls=0)
        for seed in range(8):
            _, o, _ = spot(seed, 24)
            outcomes = []
            for p in (base, null, zero):
                rng = random.Random(seed)
                result = p.choose(o, rng)
                outcomes.append((result.card, result.details.get('x8', {}).get('value'), rng.getstate()))
            self.assertEqual(outcomes[0], outcomes[1])
            self.assertEqual(outcomes[0], outcomes[2])

    def test_real_child_draws_fresh_layouts_and_stays_one_depth(self):
        p = self.make8(self.settings(), cls=ExperimentalPlayer)
        p.experiment.update(recursive='uniform', inner_layouts=3, max_calls=1)
        draws = []
        original = ExperimentalPlayer.read_layouts
        def recording(child, o, view, source, rng, n):
            result = original(child, o, view, source, rng, n)
            if child is not p:
                self.assertIs(xp.Seats, Seats)
                self.assertFalse(child.experiment.get('recursive'))
                self.assertEqual(n, 3)
                draws.append((o, result))
            return result
        before = xp.Seats
        for seed in range(8):
            _, o, _ = spot(seed, 24)
            with patch('bridge_harness.gen6.BidderState', FakeState), \
                 patch('bridge_harness.mixed_arena.Weights', FakeBelief), \
                 patch.object(ExperimentalPlayer, 'read_layouts', recording):
                p.choose(o, random.Random(seed))
            self.assertIs(xp.Seats, before)
            if draws:
                break
        self.assertTrue(draws)
        for o, result in draws:
            worlds, weights, info = result
            self.assertGreater(len(worlds), 1)
            for world in worlds:
                for seat, hand in enumerate(o.known_hands):
                    if hand is not None:
                        self.assertEqual(tuple(sorted(world[seat])), hand)

    def test_root_roll_exception_restores_factory(self):
        p = self.make8(self.settings(), cls=ExperimentalPlayer)
        p.experiment['recursive'] = 'uniform'
        before = xp.Seats
        with patch.object(xp.X8Player, 'roll', side_effect=RuntimeError('outer sentinel')):
            with self.assertRaisesRegex(RuntimeError, 'outer sentinel'):
                p.roll()
        self.assertIs(xp.Seats, before)

    def test_reader_identity_restored_on_plain_and_pooled_exceptions(self):
        from bridge_harness.gen7 import hidden_plays
        for pooled in (False, True):
            p = self.make8(dict(blind=True, names={'self': 'me', '*': '', 'they_see': ''},
                mix=dict(read_declarer=['*'], read_defender=['*']) if pooled else {}),
                cls=ExperimentalPlayer)
            p.experiment['reader_identity'] = True
            p.net.vocab = {'?': 0, 'me': 1}
            p.meet('unseen')
            exercised = False
            for seed in range(12):
                _, o, _ = spot(seed, 20)
                view = View(o)
                assign = view.uniform(4, np.random.default_rng(seed))
                p.play_cache, p.mix_cache = (None, {}), (None, {})
                with patch.object(p.net, 'log_policy_arrays', side_effect=RuntimeError('reader sentinel')):
                    try:
                        p.play_log_probabilities(o, view, assign, hidden_plays(o, True))
                    except RuntimeError as exc:
                        self.assertEqual(str(exc), 'reader sentinel')
                        exercised = True
                self.assertEqual(p.net.who, ('me', ''))
                if exercised:
                    break
            self.assertTrue(exercised)


if __name__ == '__main__':
    if '--strict-known' in sys.argv:
        sys.argv.remove('--strict-known')
        for cls in (SchedulerReview, PlayerReview):
            for value in cls.__dict__.values():
                if getattr(value, '__unittest_expecting_failure__', False):
                    value.__unittest_expecting_failure__ = False
        del cls, value
    unittest.main()
