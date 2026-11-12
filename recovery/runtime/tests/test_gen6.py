import json
import math
import os
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from bridge_harness.core import Game, card, vulnerable
from bridge_harness.corpus import generate
from bridge_harness.gen6 import Classes, Gen6Config, Gen6Player, View, player, spaced, systematic
from bridge_harness.gen6_nets import FitScorer, LeadNet, POP, hand_types
from bridge_harness.mixed_arena import ArenaPlayer
from bridge_harness.players import GreedyPlayer, PIMCPlayer
from bridge_harness.runner import play_table, replay
from bridge_harness.sampling import Sampler


def position(seed, plies):
    """A random position after `plies` cards of random legal play."""
    board = next(generate(1, seed))
    game = Game(board)
    rng = random.Random(seed)
    for _ in range(plies):
        game.play(rng.choice(game.observation().legal))
    return board, game


def scorer_weights(path, seed=0, widths=(16, 8, 8)):
    r = np.random.default_rng(seed)
    w = lambda a, b: (r.standard_normal((a, b)) / math.sqrt(a)).astype(np.float32)
    w0, w1, w2 = widths
    np.savez(path, Wh=3 * w(120, w0), Wa=w(28 * 38, w0), b0=np.zeros(w0, np.float32), W1=w(w0, w1), b1=np.zeros(w1, np.float32),
             W2=w(w1, w2), b2=np.zeros(w2, np.float32), Wo=3 * w(w2, 1), bo=np.zeros(1, np.float32))


def lead_weights(path, seed=0, h=8, g=6, peak=40.):
    r = np.random.default_rng(seed)
    w = lambda a, b, s=1.: (s * r.standard_normal((a, b)) / math.sqrt(a)).astype(np.float32)
    z = lambda n: np.zeros(n, np.float32)
    np.savez(path, Ea=w(28 * 38, h), Wh=w(83 + 256, h), b0=z(2 * h), W1=w(2 * h, 12), b1=z(12), W2=w(12, h), b2=z(h),
             Ws1=w(h, 10), bs1=z(10), Wo1=w(10, 560, peak), bo1=z(560), Ws2=w(h + 76, 10), bs2=z(10), Wo2=w(10, 560, peak), bo2=z(560),
             Wc=w(h, g), Wg=w(g + 176, 10), bg=z(10), Wgo=w(10, 32, peak), bgo=z(32))


class FakeState:
    def __init__(self, path=None):
        pass

    def final_state(self, hand, seat, dealer, vulnerability, auction):
        return np.linspace(-1, 1, 256, dtype=np.float32)


class FakeBelief:
    def __init__(self, path):
        pass

    def logits(self, o):
        return np.zeros((52, 4))


class Gen6Tests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'BRIDGE_DDS_CACHE': ''})
        self.env.start()
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        scorer_weights(self.root / 'scorer.npz')
        lead_weights(self.root / 'lead.npz')
        for name in ('belief.npz', 'bidder.keras'):
            (self.root / name).write_bytes(b'x')
        self.players = []

    def tearDown(self):
        for p in self.players:
            p.close()
        self.dir.cleanup()
        self.env.stop()

    def spec(self, **switches):
        return dict(id='6-test', engine='gen6', samples=8, near_tie=0., exploration=0., scorer='scorer.npz', lead_belief='lead.npz',
                    lead_state_bidder='bidder.keras', belief='belief.npz', belief_kind='public', gen6=switches)

    def make(self, cls=Gen6Player, **switches):
        with patch('bridge_harness.gen6.BidderState', FakeState), patch('bridge_harness.mixed_arena.Weights', FakeBelief):
            p = cls(self.spec(**switches), self.root)
        self.players.append(p)
        return p

    # ---- layouts -------------------------------------------------------------------------
    def test_deal_list_is_exactly_the_card_fit_layouts(self):
        checked = 0
        for seed in range(40):
            board, game = position(seed, 20 + seed % 20)
            o = game.observation()
            v = View(o)
            base = Sampler(o)
            self.assertEqual(v.count(), base.count(0, base.caps))
            rows = v.every()
            self.assertEqual(len(rows), v.count())
            self.assertEqual(len({r.tobytes() for r in rows}), len(rows))
            worlds = {v.world(r) for r in rows}
            truth = tuple(tuple(sorted(game.hands[s])) if o.known_hands[s] is None else o.known_hands[s] for s in range(4))
            self.assertIn(truth, worlds)
            drawn = {base.draw(random.Random(k)) for k in range(30)}
            self.assertTrue(drawn <= worlds)
            for j, s in enumerate(v.hidden):
                self.assertTrue((v.original(rows, j).sum(1) == 13).all())
            checked += len(rows)
        self.assertGreater(checked, 1000)

    def test_uniform_layouts_respect_counts_and_show_outs(self):
        for seed in (3, 11, 27):
            board, game = position(seed, 24)
            o = game.observation()
            v = View(o)
            listed = {r.tobytes() for r in v.every()}
            rows = v.uniform(500, np.random.default_rng(seed))
            self.assertTrue(all(r.tobytes() in listed for r in rows))
        board, game = position(5, 0)
        v = View(game.observation())
        rows = v.uniform(64, np.random.default_rng(1))
        self.assertEqual(len(v.hidden), 3)
        self.assertTrue(all(((rows == j).sum(1) == 13).all() for j in range(3)))

    def test_systematic_resampling_follows_weights_exactly_when_it_can(self):
        index, share = systematic(np.array([.5, 0., .25, .25]), 4, np.random.default_rng(0))
        self.assertEqual(index.tolist(), [0, 2, 3])
        self.assertEqual(share.tolist(), [.5, .25, .25])
        index, share = systematic(np.array([1e-12, 1., 1e-12]), 32, np.random.default_rng(0))
        self.assertEqual(index.tolist(), [1])
        self.assertAlmostEqual(share.sum(), 1.)

    # ---- nets ----------------------------------------------------------------------------
    def test_scorer_scores_original_hands_and_shares_equal_types(self):
        scorer = FitScorer(self.root / 'scorer.npz')
        board, game = position(9, 24)
        o = game.observation()
        v = View(o)
        rows = v.every()
        for j, seat in enumerate(v.hidden):
            member = v.original(rows, j)
            self.assertTrue((member[:, v.played[seat]] == 1).all())
            got = scorer.seat_log_score(member, seat, o.dealer, o.vulnerability, o.auction)
            length, hon = hand_types(member)
            direct = scorer.log_score(length, hon, float(vulnerable(o.vulnerability, seat)), float(vulnerable(o.vulnerability, (seat + 1) % 4)),
                                      scorer.auction_part(o.auction, o.dealer, seat))
            np.testing.assert_allclose(got, direct, atol=1e-6)
            self.assertTrue((got <= 0).all())
        swapped = scorer.auction_part(o.auction, o.dealer, v.hidden[0]) - scorer.auction_part(o.auction, o.dealer, v.hidden[1])
        self.assertGreater(float(np.abs(swapped).max()), 0)      # the auction is seen from the hand's own seat

    def test_lead_net_draws_legal_layouts_with_the_stated_probabilities(self):
        net = LeadNet(self.root / 'lead.npz', FakeState())
        board, game = position(4, 0)
        o = game.observation()
        hand = o.known_hands[o.controller]
        c = net.context(hand, o.controller, o.dealer, o.vulnerability, o.auction)
        rng = np.random.default_rng(2)
        types = net.sample(c, 6000, rng)
        d_len, d_hon, m_len, m_hon = types
        own_len, own_hon = hand_types(np.isin(np.arange(52), hand).astype(np.int8))
        self.assertTrue((d_len + m_len <= 13 - own_len).all())
        self.assertTrue(((d_hon & m_hon) == 0).all() and ((d_hon | m_hon) & own_hon == 0).all())
        self.assertTrue((POP[d_hon] <= d_len).all() and (POP[m_hon] <= m_len).all())
        for d, m, p in LeadNet.deal(hand, tuple(x[:200] for x in types), rng):
            self.assertEqual(sorted(d + m + p + tuple(hand)), list(range(52)))
        keys = [tuple(np.concatenate([a, b, e, f])) for a, b, e, f in zip(*types)]
        top = max(set(keys), key=keys.count)
        k = keys.index(top)
        stated = math.exp(net.log_type_prob(c, *(x[k:k + 1] for x in types))[0])
        observed = keys.count(top) / len(keys)
        self.assertGreater(observed, .01)
        self.assertLess(abs(observed - stated), 5 * math.sqrt(stated * (1 - stated) / len(keys)))
        density = net.log_density(c, *(x[:50] for x in types))
        self.assertTrue((density <= net.log_type_prob(c, *(x[:50] for x in types)) + 1e-9).all())

    def test_lead_net_only_accepts_auctions_inside_its_window(self):
        self.assertTrue(LeadNet.fits(('PASS',) * 25))
        self.assertFalse(LeadNet.fits(('PASS',) * 26))

    # ---- decisions -----------------------------------------------------------------------
    def test_settings_are_validated(self):
        for bad in (dict(lead_source='bidder'), dict(early_source='lead_net'), dict(list_from_trick=0), dict(list_from_trick=15),
                    dict(lead_pool=0), dict(early_pick='best'), dict(list_solve=-1), dict(list_max_layouts=0), dict(list_solve=1.5),
                    dict(mid_samples=0), dict(mid_from_trick=0), dict(cluster_pool=0)):
            with self.assertRaises(ValueError):
                Gen6Config(**bad)
        with self.assertRaises(TypeError):
            Gen6Config(unknown=1)
        spec = self.spec(early_source='gen5')
        spec.pop('belief')
        with patch('bridge_harness.gen6.BidderState', FakeState), self.assertRaises(ValueError):
            Gen6Player(spec, self.root)

    def test_phases_follow_the_switches(self):
        p = self.make(list_from_trick=6)
        late = self.make(list_from_trick=9)
        never = self.make(list_from_trick=14)
        short = self.make(list_from_trick=6, list_max_layouts=100)
        seen = set()
        for plies in (0, 1, 7, 19, 20, 30, 33, 44):
            board, game = position(21, plies)
            o = game.observation()
            if len(o.legal) == 1:
                continue
            v = View(o)
            trick = plies // 4 + 1
            want = 'lead_net' if plies == 0 else 'list' if trick >= 6 else 'scorer'
            self.assertEqual(p.source(o, v), want)
            self.assertEqual(late.source(o, v), 'lead_net' if plies == 0 else 'list' if trick >= 9 else 'scorer')
            self.assertEqual(never.source(o, v), 'lead_net' if plies == 0 else 'scorer')
            self.assertEqual(short.source(o, v), 'lead_net' if plies == 0 else 'list' if trick >= 6 and v.count() <= 100 else 'scorer')
            d = p.choose(o, random.Random(plies)).details
            self.assertEqual(d['gen6']['source'], {'list': 'deal_list'}.get(want, want))
            self.assertEqual(d['gen6']['trick'], trick)
            self.assertLessEqual(d['selected_pimc_gap'], 1e-9)
            self.assertAlmostEqual(sum(d['behavior_probabilities'].values()), 1.)
            best = min(e['gap_to_best'] for e in d['estimates'].values())
            self.assertEqual(best, 0.)
            self.assertTrue(all(e['gap_to_best'] <= 1e-9 for c, e in d['estimates'].items() if d['behavior_probabilities'][c] > 0))
            if want == 'list':
                self.assertEqual(d['gen6']['listed'], v.count())
                self.assertLessEqual(d['samples'], max(1, p.config.list_solve))
            else:
                self.assertLessEqual(d['samples'], 8 if trick < 3 else 64)
                if want == 'scorer':
                    self.assertEqual(d['gen6']['draws'], 8 if trick < 3 else 64)
            json.dumps(d, allow_nan=False)
            seen.add(want)
        self.assertEqual(seen, {'lead_net', 'scorer', 'list'})

    def test_whole_list_is_solved_with_scorer_weights_when_asked(self):
        p = self.make(list_from_trick=6, list_solve=0)
        board, game = position(8, 32)
        o = game.observation()
        v = View(o)
        worlds, weights, info = p.layouts(o, v, 'list', np.random.default_rng(0))
        self.assertEqual(len(worlds), v.count())
        self.assertAlmostEqual(float(weights.sum()), 1.)
        rows = v.every()
        logw = sum(p.scorer.seat_log_score(v.original(rows, j), s, o.dealer, o.vulnerability, o.auction) for j, s in enumerate(v.hidden))
        np.testing.assert_allclose(weights, np.exp(logw) / np.exp(logw).sum(), rtol=1e-9)
        self.assertEqual(worlds, [v.world(r) for r in rows])
        capped = self.make(list_from_trick=6, list_solve=5)
        w2, weights2, _ = capped.layouts(o, v, 'list', np.random.default_rng(0))
        self.assertLessEqual(len(w2), 5)
        self.assertTrue(set(w2) <= set(worlds))
        self.assertTrue(np.allclose(weights2 * 5, np.round(weights2 * 5)))

    def test_classes_carry_the_same_posterior_as_listing_every_layout(self):
        p = self.make()
        checked = 0
        for seed in range(12):
            board, game = position(seed, 21 + 2 * seed)
            o = game.observation()
            v = View(o)
            if v.count() > 20000:
                continue
            classes = Classes(v)
            self.assertAlmostEqual(float(np.exp(classes.logmult).sum()), v.count(), delta=1e-6 * v.count())
            rows = v.every()
            layout_logw = p.layout_log_weights(o, v, rows)
            class_logw = classes.logmult + p.type_log_weights(o, v, classes.length, classes.hon, 'scorer')
            self.assertAlmostEqual(float(np.exp(layout_logw).sum()), float(np.exp(class_logw).sum()), delta=1e-6 * float(np.exp(layout_logw).sum()))
            # every layout belongs to exactly one class with the same types, and classes partition the weight
            key = lambda la, ha, lb, hb: tuple(map(tuple, (la, ha, lb, hb)))
            (la, ha), (lb, hb) = (hand_types(v.original(rows, j)) for j in range(2))
            by_type = {}
            for i in range(len(rows)):
                k = key(la[i], ha[i], lb[i], hb[i])
                by_type[k] = by_type.get(k, 0.) + math.exp(layout_logw[i])
            self.assertEqual(len(by_type), len(classes))
            for i in range(len(classes)):
                k = key(classes.length[0][i], classes.hon[0][i], classes.length[1][i], classes.hon[1][i])
                self.assertAlmostEqual(by_type[k], math.exp(class_logw[i]), delta=1e-6 * by_type[k])
            listed = {v.world(r) for r in rows}
            worlds = classes.worlds(range(len(classes)), np.random.default_rng(seed))
            self.assertTrue(set(worlds) <= listed)
            self.assertEqual(len(set(worlds)), len(classes))
            checked += 1
        self.assertGreater(checked, 5)

    def test_early_layouts_are_dealt_from_the_weighted_classes(self):
        board, game = position(13, 5)
        o = game.observation()
        v = View(o)
        for pick in ('spaced', 'random', 'strata', 'centres'):
            p = self.make(early_pick=pick, cluster_pool=40)
            worlds, weights, info = p.layouts(o, v, 'scorer', np.random.default_rng(0))
            self.assertAlmostEqual(float(weights.sum()), 1.)
            self.assertLessEqual(len(worlds), 8)
            self.assertEqual(len(set(worlds)), len(worlds))
            self.assertEqual(info['draws'], 8)
            if pick in ('strata', 'centres'):
                self.assertEqual((info['pool'], info['clusters'] <= 8), (40, True))
                self.assertTrue(np.allclose(weights * 40, np.round(weights * 40)))      # cluster sizes out of the pool
                d = p.choose(o, random.Random(2)).details
                self.assertEqual((d['gen6']['pick'], d['gen6']['source']), (pick, 'scorer'))
                self.assertLessEqual(d['selected_pimc_gap'], 1e-9)
            more = self.make(early_pick=pick, mid_from_trick=2, mid_samples=20)
            self.assertEqual(more.layouts(o, v, 'scorer', np.random.default_rng(0))[2]['draws'], 20)
            self.assertEqual(info['classes'], len(Classes(v)))
            self.assertGreaterEqual(info['effective'], 1.)
            for w in worlds:
                self.assertEqual(sorted(c for h in w for c in h), sorted(set(range(52)) - {c for _, c in o.history}))
                self.assertEqual([w[s] for s in range(4) if o.known_hands[s] is not None], [h for h in o.known_hands if h is not None])
        picks = spaced(np.log(np.array([.5, 1e-9, .25, .25])), 4, .5)
        self.assertEqual(picks.tolist(), [0, 0, 2, 3])

    def test_scorer_can_make_the_opening_lead_from_a_weighted_pool(self):
        p = self.make(lead_source='scorer', lead_pool=256)
        board, game = position(6, 0)
        o = game.observation()
        v = View(o)
        self.assertEqual(p.source(o, v), 'scorer')
        worlds, weights, info = p.layouts(o, v, 'scorer', np.random.default_rng(0))
        self.assertEqual(info['pool'], 256)
        self.assertAlmostEqual(float(weights.sum()), 1.)
        d = p.choose(o, random.Random(1)).details
        self.assertEqual(d['gen6']['source'], 'scorer')
        long_auction = self.make()
        with patch.object(LeadNet, 'fits', return_value=False):
            self.assertEqual(long_auction.source(o, v), 'scorer')

    def test_leader_can_weight_early_layouts_with_the_lead_net(self):
        p = self.make(leader_early_source='lead_net')
        board, game = position(17, 0)
        game.play(game.observation().legal[0])
        while True:                       # reach the opening leader's next turn
            o = game.observation()
            if o.controller == (o.contract.declarer + 1) % 4 and len(o.legal) > 1 and len(o.history) < 20:
                break
            game.play(o.legal[0])
        v = View(o)
        self.assertEqual(p.source(o, v), 'lead_net')
        rows = v.uniform(50, np.random.default_rng(3))
        logw = p.layout_log_weights(o, v, rows, 'lead_net')
        self.assertTrue(np.isfinite(logw).all())
        self.assertGreater(float(np.ptp(logw)), 0)
        d = p.choose(o, random.Random(1)).details
        self.assertEqual(d['gen6']['source'], 'lead_net')
        self.assertEqual(d['gen6']['classes'], len(Classes(v)))
        self.assertEqual(self.make().source(o, v), 'scorer')

    def test_gen5_switches_reproduce_the_arena_player_exactly(self):
        six = self.make(lead_source='gen5', early_source='gen5', list_from_trick=14)
        five = self.make(ArenaPlayer)
        for plies in (0, 3, 14, 26, 41):
            board, game = position(31, plies)
            o = game.observation()
            a = six.choose(o, random.Random(plies))
            b = five.choose(o, random.Random(plies))
            self.assertEqual(a.card, b.card)
            details = dict(a.details)
            if not details.get('forced'):
                self.assertEqual(details.pop('gen6')['source'], 'gen5')
            self.assertEqual(details, b.details)

    def test_policy_chooses_only_among_tied_cards_by_the_arena_rule(self):
        class Stub:
            def __init__(self):
                self.seen = []

            def choose(self, o, details, rng):
                self.seen.append(details['samples'])
                cards = sorted(card(c) for c, p in details['behavior_probabilities'].items() if p > 0)
                return cards[-1], {c: float(i) for i, c in enumerate(cards)}
        six = self.make(list_from_trick=6, list_solve=0)
        five = self.make(ArenaPlayer)
        six.selector, five.selector = Stub(), Stub()
        used = 0
        for seed in range(30):
            board, game = position(seed, 24 + seed % 16)
            o = game.observation()
            if len(o.legal) == 1:
                continue
            search = six.search_decision(o, random.Random(seed), *self.solved(six, o), dict(source='test'))
            eligible = [card(c) for c, p in search.details['behavior_probabilities'].items() if p > 0]
            got = six.break_ties(o, random.Random(seed), search)
            self.assertIn(got.card, eligible)
            self.assertLessEqual(got.details['selected_pimc_gap'], 1e-9)
            if len(eligible) < 2:
                self.assertIs(got, search)
                continue
            used += 1
            self.assertEqual(got.card, max(eligible))
            self.assertEqual(got.details['proposal_probabilities'], search.details['behavior_probabilities'])
            with patch.object(PIMCPlayer, 'choose', return_value=search):
                reference = five.choose(o, random.Random(seed))
            self.assertEqual(got.card, reference.card)
            self.assertEqual(got.details, reference.details)
            self.assertTrue(32 <= six.selector.seen[-1] <= 192)
        self.assertGreater(used, 5)

    def solved(self, p, o):
        v = View(o)
        worlds, weights, _ = p.layouts(o, v, 'list', np.random.default_rng(0))
        before = p.dds.cache_stats()
        solved = p.dds.solve_batch(worlds, o.contract.trump, o.leader, o.trick, fixed_seats=[s for s, h in enumerate(o.known_hands) if h is not None])
        return solved, weights, before, p.dds.cache_stats()

    def test_full_tables_are_legal_and_replay(self):
        six = self.make(list_solve=16)
        players = {'6': six, 'g': GreedyPlayer()}
        sources = set()
        for seed in (2, 3):
            board = next(generate(1, 700 + seed))
            for room in (0, 1):
                result = play_table(board, ['6' if s % 2 == room else 'g' for s in range(4)], players, seed=5)
                self.assertEqual(result['status'], 'ok', result.get('traceback'))
                replay(dict(board=board.to_dict(), tables=[result]))
                json.dumps(result, allow_nan=False)
                sources |= {a['gen6']['source'] for a in result['actions'] if a['player'] == '6' and 'gen6' in a}
        self.assertEqual(sources, {'lead_net', 'scorer', 'deal_list'})

    def test_factory_gives_other_specs_the_unchanged_arena_player(self):
        with patch('bridge_harness.gen6.BidderState', FakeState), patch('bridge_harness.mixed_arena.Weights', FakeBelief):
            a = player(self.spec(), self.root)
            b = player(dict(id='5', samples=8, near_tie=0.), self.root)
        self.players += [a, b]
        self.assertIs(type(a), Gen6Player)
        self.assertIs(type(b), ArenaPlayer)


if __name__ == '__main__':
    unittest.main()
