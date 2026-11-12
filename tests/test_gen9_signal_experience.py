"""Gen 9 card-play experience (G9-S5): occasions, honesty and play-factor estimates from finished boards."""
import random
import unittest

import numpy as np

from bridge_harness import experience as xp
from bridge_harness.corpus import generate
from bridge_harness.players import Decision, GreedyPlayer
from bridge_harness.runner import play_table
from bridge_harness.signal_experience import FACTOR_GRID, card_stats, honesty, occasions, phi, play_info, replay_plays
from bridge_harness.signals import SPOT, SignalModel, situation
from test_gen9_signals import STANDARD


class SimulatedSignaller:
    """Greedy card play whose defenders choose among the class by a SignalModel, the class being every card of it held."""

    def __init__(self, model):
        self.model, self.greedy = model, GreedyPlayer()

    def choose(self, o, rng):
        base = self.greedy.choose(o, rng).card
        c = o.contract
        if o.actor in (c.declarer, c.dummy):
            return Decision(base, {})
        i = len(o.history)
        sit = situation(o.history + ((o.actor, base),), i, c)
        kind = self.model.signal(sit[0]) if sit else None
        if kind in (None, 'none'):
            return Decision(base, {})
        suit, lead = base // 13, sit[0] == 'lead.opening'
        if not lead and base % 13 > SPOT:
            return Decision(base, {})
        choices = [x for x in o.legal if x // 13 == suit and (lead or x % 13 <= SPOT)]
        if len(choices) < 2:
            return Decision(base, {})
        hand = o.original_hand(o.actor)
        led_suit = o.trick[0][1] // 13 if o.trick else suit
        dist = self.model.distribution(sit[0], kind, choices, hand, suit, c.trump, led_suit, c.trump == 4,
                                       [x for x in hand if x // 13 == suit] if lead else None)
        ticket = rng.random()
        for x in sorted(dist):
            ticket -= dist[x]
            if ticket <= 0:
                return Decision(x, {})
        return Decision(choices[-1], {})


def simulate(h, eps, boards, seed):
    model = SignalModel(STANDARD, h, eps)
    sim = SimulatedSignaller(model)
    store = xp.empty('sim')
    for k, board in enumerate(generate(boards, seed)):
        side = 1 - board.contract.declarer % 2
        result = play_table(board, [0, 1, 0, 1], {0: sim, 1: sim}, seed=k)
        assert result['status'] == 'ok', result.get('traceback')
        plays = replay_plays(board, result['actions'])
        store = xp.add(store, xp.delta('sim', f'b{k}', card_stats(board, plays, model, side)))
    return model, store


class HonestyTests(unittest.TestCase):
    def test_a_known_honesty_is_recovered_within_its_interval(self):
        for h, eps in ((.9, .05), (.5, .05), (.2, 0.)):
            model, store = simulate(h, eps, 150, 40 + int(10 * h))
            stats = store['stats']
            total = sum(v for s in stats.values() for k, v in s['n'].items() if k.count('/') == 1 and k.startswith('all'))
            self.assertGreater(total, 150)
            pooled = {'kind': 'count', 'n': {}}
            for s in stats.values():
                pooled = xp.merge_stat(pooled, s)
            mean, sd = honesty(pooled, prior_mean=.5, prior_n=2., eps=eps)
            self.assertLess(abs(mean - h), 3 * sd + .02, (h, mean, sd, total))
            self.assertLess(sd, .08)

    def test_the_floor_is_allowed_for_by_the_class_size_labels(self):
        model, store = simulate(.9, .2, 150, 77)
        pooled = {'kind': 'count', 'n': {}}
        for s in store['stats'].values():
            pooled = xp.merge_stat(pooled, s)
        exact, sd = honesty(pooled, prior_mean=.5, prior_n=2., eps=.2)
        aggregate = honesty({'kind': 'count', 'n': {k: v for k, v in pooled['n'].items() if k.count('/') == 1}}, prior_mean=.5, prior_n=2., eps=.2)[0]
        self.assertLess(abs(exact - .9), 3 * sd + .02)
        self.assertNotAlmostEqual(exact, aggregate, places=3)

    def test_no_data_gives_the_prior_and_only_signal_occasions_count(self):
        self.assertAlmostEqual(honesty(None, prior_mean=.7, prior_n=8.)[0], .7, places=1)
        board = next(generate(1, 5))
        result = play_table(board, [0, 1, 0, 1], {0: GreedyPlayer(), 1: GreedyPlayer()}, seed=1)
        plays = replay_plays(board, result['actions'])
        self.assertEqual(occasions(board, plays, SignalModel({}), 0), [])
        for key, n, s, hit in occasions(board, plays, SignalModel(STANDARD), 1 - board.contract.declarer % 2):
            self.assertGreaterEqual(s, 2)
            self.assertIn(n, (2, s))


class DeltaTests(unittest.TestCase):
    def test_card_delta_is_the_boards_card_stats(self):
        from bridge_harness.signal_experience import card_delta
        model, store = simulate(.7, 0., 3, 11)
        board = next(generate(1, 11))
        side = 1 - board.contract.declarer % 2
        sim = SimulatedSignaller(model)
        plays = replay_plays(board, play_table(board, [0, 1, 0, 1], {0: sim, 1: sim}, seed=0)['actions'])
        d = card_delta('g', 'k', board, plays, dict(descriptor=STANDARD), side)
        self.assertEqual(d['stats'], card_stats(board, plays, model, side))
        self.assertEqual(card_delta('g', 'k', board, plays, None, side)['stats'], {})


class EmissionTests(unittest.TestCase):
    def test_an_asymmetric_emitter_is_recovered(self):
        from bridge_harness.signal_experience import emission, emission_stats
        truth = [[.70, .22, .08], [.88, .05, .07]]                     # BEN-like count on declarer's lead: low by default
        model = SignalModel(STANDARD, 1., 0., emission={'declarer_lead.count': truth})
        sim = SimulatedSignaller(model)
        store = xp.empty('e')
        for k, board in enumerate(generate(400, 91)):
            side = 1 - board.contract.declarer % 2
            plays = replay_plays(board, play_table(board, [0, 1, 0, 1], {0: sim, 1: sim}, seed=k)['actions'])
            store = xp.add(store, xp.delta('e', f'b{k}', emission_stats(board, plays, SignalModel(STANDARD), side)))
        stat = store['stats']['card.declarer_lead.count.emit']
        rows = np.array(emission(stat, alpha=1.))
        total = sum(stat['n'].values())
        self.assertGreater(total, 300)
        self.assertLess(abs(rows[0, 1] - .22), .07)                     # P(high | even)
        self.assertLess(abs(rows[1, 1] - .05), .04)                     # P(high | odd)
        self.assertGreater(rows[0, 1] / rows[1, 1], 2.)


class PlayFactorTests(unittest.TestCase):
    def test_phi_follows_the_data_and_shrinks_to_the_prior(self):
        self.assertEqual(phi(None, prior_phi=.3), .3)
        store = xp.empty('p')
        best = FACTOR_GRID.index(1.)
        for k in range(300):
            gains = [-(g - 1.) ** 2 + random.Random(k).gauss(0, .05) for g in FACTOR_GRID]
            store = xp.add(store, xp.delta('p', f'd{k}', {'play.info': play_info(gains)}))
        self.assertEqual(phi(store['stats']['play.info'], prior_phi=.3), FACTOR_GRID[best])
        few = xp.add(xp.empty('q'), xp.delta('q', 'd0', {'play.info': play_info([-(g - 1.) ** 2 * .001 for g in FACTOR_GRID])}))
        self.assertEqual(phi(few['stats']['play.info'], prior_phi=.3), .3)


if __name__ == '__main__':
    unittest.main()
