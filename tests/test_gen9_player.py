"""Gen 9 player shell (bridge_harness/gen9.py): inert by default, the mixture over profiles, the reader hooks,
what the table tells the player, and the test-only oracle."""
import json
import math
import os
from unittest.mock import patch

import numpy as np

from bridge_harness import experience as xp
from bridge_harness.corpus import generate
from bridge_harness.gen6 import Classes, View
from bridge_harness.gen6_nets import FitScorer, HON_HCP, hand_types
from bridge_harness.gen7 import Gen7Player
from bridge_harness.gen9 import Gen9Config, Gen9Player, class_log_layouts, gen9_settings, player
from bridge_harness.player_model import PlayerModel
from bridge_harness.players import GreedyPlayer
from bridge_harness.runner import play_table, replay
from test_gen6 import FakeBelief, FakeState, scorer_weights
from test_gen7 import Fixture, played

EARLY = dict(early_play_weight=1., early_pool=64, early_min_effective=2.)       # the Gen 8 prototype's reading, small


class ToyCard:
    """A stand-in for the rule filter: every call-making seat of this partnership is said to hold 12 points or more."""
    calls = 0

    def type_log_score(self, length, hon, seat, dealer, vulnerability, auction):
        ToyCard.calls += 1
        return np.where(HON_HCP[hon].sum(axis=1) >= 12, 0., -3.)


def toy_card(model, other, root):
    return ToyCard() if model.bidding.get('toy') else None


class ResidualCard:
    """A stand-in for a filter that knows each profile's residual: in full it asks for 12 points (-3 below); on the
    residual of profile 'alpha' it only asks for 8 (-1 below)."""
    asked = []

    def type_log_score(self, length, hon, seat, dealer, vulnerability, auction, profile=None):
        ResidualCard.asked.append(profile)
        points = HON_HCP[hon].sum(axis=1)
        return np.where(points >= 12, 0., -3.) if profile is None else np.where(points >= 8, 0., -1.)


def residual_card(model, other, root):
    return ResidualCard()


def _lse(rows):
    s = np.stack(rows)
    return np.log(np.exp(s - s.max(axis=0)).sum(axis=0)) + s.max(axis=0)


def lm(row, ref=None):
    """log of the mean of exp(row) over the layouts (rows weighted by exp(ref))."""
    w = np.ones(len(row)) if ref is None else np.exp(ref - np.max(ref))
    return float(np.log((np.exp(row - row.max()) * w).sum() / w.sum()) + row.max())


class Shell(Fixture):
    def make9(self, cls=Gen9Player, gen9=None, gen7=None, engine='gen9', **switches):
        spec = dict(id='9-test', engine=engine, samples=8, near_tie=0., exploration=0., scorer='scorer.npz', lead_belief='lead.npz',
                    lead_state_bidder='bidder.keras', belief='belief.npz', belief_kind='public', gen6=switches,
                    gen7_policy='gen7.npz', gen7=gen7 or {})
        if gen9 is not None:
            spec['gen9'] = gen9
        with patch('bridge_harness.gen6.BidderState', FakeState), patch('bridge_harness.mixed_arena.Weights', FakeBelief):
            p = cls(spec, self.root)
        self.players.append(p)
        return p

    def table(self, p, board, room, seed=5):
        result = play_table(board, ['x' if s % 2 == room else 'g' for s in range(4)], {'x': p, 'g': GreedyPlayer()}, seed=seed)
        self.assertEqual(result['status'], 'ok', result.get('traceback'))
        replay(dict(board=board.to_dict(), tables=[result]))
        json.dumps(result, allow_nan=False)
        return result

    def two_hidden(self, seeds, plies, declarer=None):
        """Positions with two hidden hands and a choice; `declarer` True/False keeps only declarer's / a defender's."""
        for seed in seeds:
            for n in plies:
                board, game, before = played(seed, n)
                o = game.observation()
                declaring = o.controller % 2 == o.contract.declarer % 2
                if len(View(o).hidden) == 2 and len(o.legal) > 1 and declarer in (None, declaring):
                    yield o, game


class InertTests(Shell):
    def test_settings(self):
        self.assertEqual(gen9_settings(None)[0], Gen9Config())
        for bad in (dict(max_profiles=0), dict(card_weight=-1), dict(factor_min_plays=0), dict(surprise=1)):
            with self.assertRaises(ValueError):
                gen9_settings(bad)

    def test_plain_models_play_the_gen8_game_card_for_card(self):
        eight = self.make9(Gen7Player, gen7=EARLY, engine='gen7', list_solve=16)
        nine = self.make9(gen7=EARLY, gen9=dict(models={'ben': dict(kind='outside'), '*': dict(kind='unknown')}), list_solve=16)
        nine.meet('ben')
        nine.auction_by(['6-32'] * 4)
        compared = 0
        for seed in (2, 3):
            board = next(generate(1, 700 + seed))
            for room in (0, 1):
                a, b = self.table(eight, board, room), self.table(nine, board, room)
                self.assertEqual([x['card'] for x in a['actions']], [x['card'] for x in b['actions']])
                for x, y in zip(a['actions'], b['actions']):
                    if x['player'] == 'x' and 'gen6' in x:
                        self.assertEqual(x['estimates'], y['estimates'])
                        self.assertEqual(x['behavior_probabilities'], y['behavior_probabilities'])
                        self.assertEqual({k: v for k, v in x['gen6'].items() if not k.endswith('seconds')},
                                         {k: v for k, v in y['gen6'].items() if not k.endswith('seconds')})
                        compared += 1
        self.assertGreater(compared, 40)

    def test_factory(self):
        spec = dict(id='9-test', engine='gen9', samples=8, near_tie=0., exploration=0., scorer='scorer.npz', lead_belief='lead.npz',
                    lead_state_bidder='bidder.keras', belief='belief.npz', belief_kind='public', gen6={}, gen7_policy='gen7.npz', gen7={})
        with patch('bridge_harness.gen6.BidderState', FakeState), patch('bridge_harness.mixed_arena.Weights', FakeBelief):
            nine, seven = player(spec, self.root), player(dict(spec, engine='gen7'), self.root)
        self.players += [nine, seven]
        self.assertIsInstance(nine, Gen9Player)
        self.assertNotIsInstance(seven, Gen9Player)
        self.assertIsInstance(seven, Gen7Player)


class CallsTests(Shell):
    def scorers(self):
        out = {}
        for k, name in enumerate(('alpha', 'beta', None)):
            path = self.root / f'scorer_{k}.npz'
            scorer_weights(path, seed=20 + k)
            out[name] = FitScorer(path)
        return out

    def brute(self, p, o, view, length, hon, scorers, profiles, side):
        """log sum_k p_k exp(sum of S_k over that side's seats, hidden and visible); the other side by the player's own scorer."""
        total = np.zeros(len(length[0]))
        rows = []
        for system, prob in profiles:
            row = np.full(len(length[0]), math.log(prob))
            for s in (side, side + 2):
                if s in view.hidden:
                    j = view.hidden.index(s)
                    row = row + scorers[system].type_log_score(length[j], hon[j], s, o.dealer, o.vulnerability, o.auction)
                elif o.known_hands[s] is not None:
                    member = np.zeros((1, 52), np.int8)
                    member[0, list(o.original_hand(s))] = 1
                    row = row + scorers[system].seat_log_score(member, s, o.dealer, o.vulnerability, o.auction)[0]
            rows.append(row)
        stacked = np.stack(rows)
        total += np.log(np.exp(stacked - stacked.max(axis=0)).sum(axis=0)) + stacked.max(axis=0)
        for j, s in enumerate(view.hidden):
            if s % 2 != side:
                total += p.scorer.type_log_score(length[j], hon[j], s, o.dealer, o.vulnerability, o.auction)
        return total

    def test_mixture_is_over_the_whole_board_and_counts_the_visible_hand(self):
        scorers = self.scorers()
        profiles = (('alpha', .6), ('beta', .3), (None, .1))
        model = PlayerModel('them', 'outside', dict((('unknown' if s is None else s), q) for s, q in profiles))
        p = self.make9(gen9={})
        p.profile_scorer = lambda side, system: scorers[system]
        p.meet(model)
        seen = {True: 0, False: 0}
        for o, game in self.two_hidden(range(40), (1, 5, 9)):
            view = View(o)
            rng = np.random.default_rng(len(o.history))
            assign = view.uniform(48, rng)
            types = [hand_types(view.original(assign, j)) for j in range(2)]
            length, hon = [t[0] for t in types], [t[1] for t in types]
            got = p.type_log_weights(o, view, length, hon, 'scorer')
            theirs = 1 - o.controller % 2
            want = self.brute(p, o, view, length, hon, scorers, profiles, theirs)
            np.testing.assert_allclose(got, want, rtol=0, atol=1e-9)
            declaring = o.controller % 2 == o.contract.declarer % 2
            seen[declaring] += 1
            if not declaring:           # a defender sees dummy, which is theirs: it must move the mixture
                without = self.brute(p, o, view, length, hon, {k: _Blind(v) for k, v in scorers.items()}, profiles, theirs)
                self.assertGreater(float(np.abs((got - got.mean()) - (without - without.mean())).max()), 1e-6)
        self.assertGreater(min(seen.values()), 3)

    def test_one_profile_is_that_profiles_scorer(self):
        scorers = self.scorers()
        p = self.make9(gen9={})
        p.profile_scorer = lambda side, system: scorers[system]
        p.meet(PlayerModel('them', profiles={'alpha': 1.}))
        o, game = next(self.two_hidden(range(40), (5,), declarer=True))
        view = View(o)
        assign = view.uniform(32, np.random.default_rng(1))
        types = [hand_types(view.original(assign, j)) for j in range(2)]
        length, hon = [t[0] for t in types], [t[1] for t in types]
        got = p.type_log_weights(o, view, length, hon, 'scorer')
        want = sum(scorers['alpha'].type_log_score(length[j], hon[j], s, o.dealer, o.vulnerability, o.auction) for j, s in enumerate(view.hidden))
        np.testing.assert_allclose(got, want, atol=1e-9)

    def test_who_bid_is_not_who_plays(self):
        scorers = self.scorers()
        common = dict(kind='house', profiles={'beta': 1.})
        p = self.make9(gen9=dict(models={'6-32': common}))
        p.profile_scorer = lambda side, system: scorers[system]
        p.meet(PlayerModel('them', profiles={'alpha': 1.}))
        o, game = next(self.two_hidden(range(40), (5,), declarer=True))
        view = View(o)
        assign = view.uniform(32, np.random.default_rng(1))
        types = [hand_types(view.original(assign, j)) for j in range(2)]
        length, hon = [t[0] for t in types], [t[1] for t in types]
        native = p.type_log_weights(o, view, length, hon, 'scorer')
        p.auction_by(['6-32'] * 4)                      # a common auction: all four calls by the common bidder
        common_read = p.type_log_weights(o, view, length, hon, 'scorer')
        want = sum(scorers['beta'].type_log_score(length[j], hon[j], s, o.dealer, o.vulnerability, o.auction) for j, s in enumerate(view.hidden))
        np.testing.assert_allclose(common_read, want, atol=1e-9)
        self.assertGreater(float(np.abs(native - common_read).max()), 1e-6)
        p.auction_by(None)
        np.testing.assert_allclose(p.type_log_weights(o, view, length, hon, 'scorer'), native, atol=0)
        p.meet('someone-else')                          # a new opponent: each side bids for itself again
        self.assertIsNone(p.bidders)
        with self.assertRaises(ValueError):
            p.auction_by(['a', 'b'])

    def test_the_card_adds_its_term_and_can_be_switched_off(self):
        declared = dict(kind='synthetic', bidding=dict(toy=True))
        on = self.make9(gen9=dict(models={'them': declared}, bidding_reader='test_gen9_player:toy_card'))
        off = self.make9(gen9=dict(models={'them': declared}, bidding_reader='test_gen9_player:toy_card', card_weight=0.))
        half = self.make9(gen9=dict(models={'them': declared}, bidding_reader='test_gen9_player:toy_card', card_weight=.5))
        plain = self.make9(gen9={})
        for p in (on, off, half, plain):
            p.meet('them')
        o, game = next(self.two_hidden(range(40), (5,), declarer=True))
        view = View(o)
        assign = view.uniform(64, np.random.default_rng(2))
        types = [hand_types(view.original(assign, j)) for j in range(2)]
        length, hon = [t[0] for t in types], [t[1] for t in types]
        base = plain.type_log_weights(o, view, length, hon, 'scorer')
        ToyCard.calls = 0
        np.testing.assert_allclose(off.type_log_weights(o, view, length, hon, 'scorer'), base, atol=1e-9)
        self.assertEqual(ToyCard.calls, 0)
        term = sum(np.where(HON_HCP[hon[j]].sum(axis=1) >= 12, 0., -3.) for j in range(2))
        self.assertGreater(float(np.abs(term).max()), 0.)
        np.testing.assert_allclose(on.type_log_weights(o, view, length, hon, 'scorer'), base + term, atol=1e-9)
        np.testing.assert_allclose(half.type_log_weights(o, view, length, hon, 'scorer'), base + .5 * term, atol=1e-9)
        self.assertEqual(ToyCard.calls, 4)
        # a partnership that declared no bidding card gets no reader, and one whose factory declines is read without it
        nothing = self.make9(gen9=dict(models={'them': dict(bidding=dict(toy=False))}, bidding_reader='test_gen9_player:toy_card'))
        nothing.meet('them')
        np.testing.assert_allclose(nothing.type_log_weights(o, view, length, hon, 'scorer'), base, atol=1e-9)


class CardProfileTests(Shell):
    def setUp(self):
        super().setUp()
        self.o, game = next(self.two_hidden(range(40), (5,), declarer=True))
        self.view = View(self.o)
        assign = self.view.uniform(64, np.random.default_rng(4))
        types = [hand_types(self.view.original(assign, j)) for j in range(2)]
        self.length, self.hon = [t[0] for t in types], [t[1] for t in types]

    def weights(self, p):
        return p.type_log_weights(self.o, self.view, self.length, self.hon, 'scorer')

    def term(self, low, cost):
        return sum(np.where(HON_HCP[self.hon[j]].sum(axis=1) >= low, 0., cost) for j in range(2))

    def test_the_card_profile_is_the_rules_alone(self):
        p = self.make9(gen9=dict(models={'them': dict(profiles={'card': 1.}, bidding=dict(toy=True))}, bidding_reader='test_gen9_player:toy_card'))
        p.meet('them')
        np.testing.assert_allclose(self.weights(p), self.term(12, -3.), atol=1e-9)          # no scorer in it at all
        silent = self.make9(gen9=dict(models={'them': dict(profiles={'card': 1.})}))         # the profile without a card or a reader: flat
        silent.meet('them')
        self.assertLess(float(np.ptp(self.weights(silent))), 1e-12)

    def test_the_flat_profile_adds_nothing_and_bounds_what_a_wrong_reading_can_cost(self):
        scorer_weights(self.root / 'alpha.npz', seed=31)
        alpha = FitScorer(self.root / 'alpha.npz')
        o = self.o
        net = sum(alpha.type_log_score(self.length[j], self.hon[j], s, o.dealer, o.vulnerability, o.auction) for j, s in enumerate(self.view.hidden))
        flat = self.make9(gen9=dict(models={'them': dict(profiles={'flat': 1.})}))
        flat.meet('them')
        self.assertFalse(flat.opponent.plain)
        self.assertLess(float(np.ptp(self.weights(flat))), 1e-12)
        mixed = self.make9(gen9=dict(models={'them': dict(profiles={'alpha': .8, 'flat': .2})}))
        mixed.profile_scorer = lambda side, system: alpha
        mixed.meet('them')
        got = self.weights(mixed)
        # two kinds: the scorer's row relative to its own mean over the layouts, flat at its share
        np.testing.assert_allclose(got, np.logaddexp(math.log(.8) + net - lm(net), math.log(.2)), atol=1e-9)
        self.assertAlmostEqual(lm(got), 0., places=9)                        # the mixture's mean over the layouts is one
        self.assertTrue(np.all(got >= math.log(.2) - 1e-12))                 # no layout falls below the flat share
        self.assertTrue(np.all(got >= math.log(.8) + net - lm(net) - 1e-12)) # and none more than -log 0.8 below the scorer alone

    def test_net_profiles_get_the_residual_and_the_mixture_weighs_both(self):
        scorer_weights(self.root / 'alpha.npz', seed=31)
        alpha = FitScorer(self.root / 'alpha.npz')
        model = dict(profiles={'alpha': .7, 'card': .3}, bidding=dict(toy=True))
        p = self.make9(gen9=dict(models={'them': model}, bidding_reader='test_gen9_player:residual_card'))
        p.profile_scorer = lambda side, system: alpha
        p.meet('them')
        ResidualCard.asked = []
        got = self.weights(p)
        self.assertEqual(sorted(set(map(str, ResidualCard.asked))), ['None', 'alpha'])
        o = self.o
        net = sum(alpha.type_log_score(self.length[j], self.hon[j], s, o.dealer, o.vulnerability, o.auction) for j, s in enumerate(self.view.hidden))
        a, c = net + self.term(8, -1.), self.term(12, -3.)
        want = np.logaddexp(math.log(.7) + a - lm(a), math.log(.3) + c - lm(c))          # each kind relative to its own mean
        np.testing.assert_allclose(got, want, atol=1e-9)
        # a reader that cannot give a residual is left off the net profile when the card profile is a candidate
        q = self.make9(gen9=dict(models={'them': model}, bidding_reader='test_gen9_player:toy_card'))
        q.profile_scorer = lambda side, system: alpha
        q.meet('them')
        np.testing.assert_allclose(self.weights(q), np.logaddexp(math.log(.7) + net - lm(net), math.log(.3) + c - lm(c)), atol=1e-9)

    def test_card_and_flat_do_not_count_against_the_number_of_profiles_kept(self):
        scorer_weights(self.root / 'alpha.npz', seed=31)
        alpha = FitScorer(self.root / 'alpha.npz')
        asked = []
        p = self.make9(gen9=dict(max_profiles=1, bidding_reader='test_gen9_player:toy_card'))
        p.profile_scorer = lambda side, system: (asked.append(system), alpha)[1]
        p.meet(PlayerModel('them', 'guest', {'alpha': .3, 'beta': .2, 'card': .4, 'flat': .1}, bidding=dict(toy=True)))
        got = self.weights(p)
        self.assertEqual(set(asked), {'alpha'})                                # one net kept, the more probable one
        o = self.o
        net = sum(alpha.type_log_score(self.length[j], self.hon[j], s, o.dealer, o.vulnerability, o.auction) for j, s in enumerate(self.view.hidden))
        c = self.term(12, -3.)
        want = _lse([math.log(.3 / .8) + net - lm(net), math.log(.4 / .8) + c - lm(c), math.log(.1 / .8) + np.zeros(len(net))])
        np.testing.assert_allclose(got, want, atol=1e-9)

    def test_kinds_are_weighed_by_layouts_when_the_rows_are_classes(self):
        scorer_weights(self.root / 'alpha.npz', seed=31)
        alpha = FitScorer(self.root / 'alpha.npz')
        model = PlayerModel('them', 'guest', {'alpha': .5, 'card': .3, 'flat': .2}, bidding=dict(toy=True))
        p = self.make9(gen7=EARLY, gen9=dict(bidding_reader='test_gen9_player:toy_card'))
        p.profile_scorer = lambda side, system: alpha
        p.meet(model)
        checked = 0
        for o, game in self.two_hidden(range(30), (1, 5, 9), declarer=True):
            view = View(o)
            classes = Classes(view)
            np.testing.assert_allclose(class_log_layouts(view, classes.length[0], classes.hon[0]), classes.logmult, atol=1e-9)
            seats = list(enumerate(view.hidden))
            net = sum(alpha.type_log_score(classes.length[j], classes.hon[j], s, o.dealer, o.vulnerability, o.auction) for j, s in seats)
            card = sum(np.where(HON_HCP[classes.hon[j]].sum(axis=1) >= 12, 0., -3.) for j, s in seats)
            ref = classes.logmult
            want = _lse([math.log(.5) + net - lm(net, ref), math.log(.3) + card - lm(card, ref), math.log(.2) + np.zeros(len(net))])
            seen = []
            real = p.read_calls
            p.read_calls = lambda *a, **k: (seen.append(k.get('ref')), real(*a, **k))[1]
            p.class_rows = True                                 # as layouts() sets it
            got = p.type_log_weights(o, view, classes.length, classes.hon, 'scorer')
            p.read_calls = real
            np.testing.assert_allclose(got, want, atol=1e-9)
            np.testing.assert_allclose(seen[0], ref, atol=1e-9)
            self.assertFalse(p.class_rows)                      # used once
            self.assertAlmostEqual(lm(got, ref), 0., places=9)  # mean over the layouts is one
            # through the engine: layouts() tells the reader its rows are classes, and layout pools say they are not
            seen.clear()
            p.read_calls = lambda *a, **k: (seen.append(k.get('ref')), real(*a, **k))[1]
            p.layouts(o, view, p.source(o, view), np.random.default_rng(1))
            p.read_calls = real
            if p.source(o, view) != 'list':
                self.assertIsNotNone(seen[0])
                self.assertEqual(len(seen[0]), len(classes))
            else:
                self.assertTrue(all(r is None for r in seen))
            checked += 1
        self.assertGreater(checked, 4)


class ToyReplay:
    """A stand-in for a replay reader: it holds the bidders of profiles 'alpha' (a hand with 13 points or more is 20
    times as likely to have made the calls) and 'alef' (9 points or more, and the calls are rarer under it)."""
    def type_log_score(self, length, hon, seat, dealer, vulnerability, auction, profile=None):
        if profile == 'alpha':
            return np.where(HON_HCP[hon].sum(axis=1) >= 13, 0., -3.) - 2.
        if profile == 'alef':
            return np.where(HON_HCP[hon].sum(axis=1) >= 9, 0., -3.) - 5.
        return None


def toy_replay(model, other, root):
    return ToyReplay() if model.id == 'them' else None


class ReplayTests(Shell):
    def test_replay_rereads_the_pool_and_only_for_the_profiles_it_holds(self):
        scorer_weights(self.root / 'alpha.npz', seed=31)
        scorer_weights(self.root / 'beta.npz', seed=32)
        scorers = {'alpha': FitScorer(self.root / 'alpha.npz'), 'beta': FitScorer(self.root / 'beta.npz')}
        scorers['alef'] = scorers['beta']
        model = dict(profiles={'alpha': .6, 'alef': .4})
        p = self.make9(gen7=EARLY, gen9=dict(models={'them': model, 'others': model}, replay_reader='test_gen9_player:toy_replay'))
        q = self.make9(gen7=EARLY, gen9=dict(models={'them': model}))
        for x in (p, q):
            x.profile_scorer = lambda side, system: scorers[system]
            x.meet('them')
        checked = 0
        for o, game in self.two_hidden(range(40), (5, 9), declarer=True):
            view = View(o)
            assign = view.uniform(64, np.random.default_rng(3))
            types = [hand_types(view.original(assign, j)) for j in range(2)]
            length, hon = [t[0] for t in types], [t[1] for t in types]
            drawn = p.type_log_weights(o, view, length, hon, 'scorer')                 # how the pool was drawn: scorers only
            np.testing.assert_allclose(drawn, q.type_log_weights(o, view, length, hon, 'scorer'), atol=1e-12)
            change = p.replay_correction(o, view, assign)
            alpha = sum(np.where(HON_HCP[hon[j]].sum(axis=1) >= 13, 0., -3.) - 2. for j in range(2))
            alef = sum(np.where(HON_HCP[hon[j]].sum(axis=1) >= 9, 0., -3.) - 5. for j in range(2))
            want = np.logaddexp(math.log(.6) + alpha, math.log(.4) + alef)              # both by replay: likelihoods, mixed as they are
            np.testing.assert_allclose(drawn + change, want, atol=1e-9)
            self.assertIsNone(q.replay_correction(o, view, assign))
            # in the reading itself: the same change, over the exponent the caller applies
            np.testing.assert_allclose(p.play_log_likelihood(o, view, assign) - q.play_log_likelihood(o, view, assign),
                                       change / p.reading_exponent(o, view), atol=1e-9)
            checked += 1
        self.assertGreater(checked, 3)
        p.meet('others')                                # a partnership the factory declines: nothing changes
        o, game = next(self.two_hidden(range(40), (5,), declarer=True))
        view = View(o)
        self.assertIsNone(p.replay_correction(o, view, view.uniform(16, np.random.default_rng(0))))
        # a candidate the reader does not hold, or a card or flat profile: the kinds were weighed over all layouts
        # when the pool was drawn, so the pool stands
        for profiles in ({'alpha': .6, 'beta': .4}, {'alpha': .9, 'flat': .1}, {'alpha': .5, 'alef': .3, 'card': .2}):
            p.meet(PlayerModel('them', 'guest', profiles))
            self.assertIsNone(p.replay_correction(o, view, view.uniform(16, np.random.default_rng(0))))
        p.meet(PlayerModel('them', 'house', {'alpha': 1.}))    # one held profile: the replay alone
        assign = view.uniform(16, np.random.default_rng(0))
        types = [hand_types(view.original(assign, j)) for j in range(2)]
        change = p.replay_correction(o, view, assign)
        rep = sum(np.where(HON_HCP[types[j][1]].sum(axis=1) >= 13, 0., -3.) - 2. for j in range(2))
        np.testing.assert_allclose(p.type_log_weights(o, view, [t[0] for t in types], [t[1] for t in types], 'scorer') + change, rep, atol=1e-9)


class CardsTests(Shell):
    STANDARD = dict(length_lead_vs_suit='4th', length_lead_vs_nt='4th', lead_from_ak='ace', honor_sequence_lead='top', attitude='standard',
                    count='standard', signal_on_partner_lead='attitude', signal_on_declarer_lead='count', first_discard='attitude', trump_signal='none')

    def test_the_signal_part_is_not_tempered(self):
        models = {'x': dict(kind='synthetic', carding=dict(descriptor=self.STANDARD, honesty=.8))}
        p = self.make9(gen7=dict(play_weight=.5, early_play_weight=.25, early_pool=64), gen9=dict(models=models), list_from_trick=7)
        p.meet('x')
        seen = set()
        for o, game in self.two_hidden(range(60), (9, 14, 30, 34), declarer=True):
            view = View(o)
            source = p.source(o, view)
            if source == 'list' and view.count() > 2000:
                continue
            assign = view.every() if source == 'list' else view.uniform(48, np.random.default_rng(1))
            net, signal = p.play_log_terms(o, view, assign)
            if not signal.any():
                continue
            exponent = .5 if source == 'list' else .25
            self.assertEqual(p.reading_exponent(o, view), exponent)
            got = p.play_log_likelihood(o, view, assign)
            np.testing.assert_allclose(exponent * got, exponent * net + signal, atol=1e-9)      # what the caller ends up with
            seen.add(source)
        self.assertEqual(len(seen), 2)


class _Blind:
    """A scorer that cannot see a visible hand (seat_log_score is zero): what the mixture would be without dummy."""
    def __init__(self, scorer):
        self.scorer = scorer

    def type_log_score(self, *a):
        return self.scorer.type_log_score(*a)

    def seat_log_score(self, member, *a):
        return np.zeros(len(member))


class TableTests(Shell):
    def test_meet_resolves_and_experience_sets_the_factor(self):
        grid = [0., .3, 1.]
        little = xp.snapshot(dict(xp.empty('ben'), boards=3, stats={'play.info': dict(kind='moment', grid=grid, n=20., sum=[0., 2., 30.], sumsq=[0., 1., 60.])}), 'e1')
        plenty = xp.snapshot(dict(xp.empty('ben'), boards=90, stats={'play.info': dict(kind='moment', grid=grid, n=900., sum=[0., 300., 100.], sumsq=[0., 400., 900.])}), 'e2')
        p = self.make9(gen7=dict(opponent_play_weight={'ben': .5, '*': .25}),
                       gen9=dict(models={'ben': dict(kind='outside', carding=dict(count='standard'))}))
        p.meet('ben')
        self.assertEqual((p.opponent.id, p.opponent.kind, p.opponent_factor), ('ben', 'outside', .5))
        p.meet('stranger')
        self.assertTrue(p.opponent.plain)
        self.assertEqual(p.opponent_factor, .25)
        p.meet(PlayerModel('ben', 'outside', experience=little))            # too few occasions: Gen 8's factor stands
        self.assertEqual(p.opponent_factor, .5)
        p.meet(PlayerModel('ben', 'outside', experience=plenty))            # enough: the factor with the best mean gain
        self.assertEqual(p.opponent_factor, .3)
        self.assertEqual(p.opponent.snapshot, 'e2')

    def test_meet_and_auction_by_take_the_profiles_from_experience(self):
        stats = {'profile': dict(kind='loglik', n=9., ll={'alpha': -30., 'beta': -5.})}
        seen = PlayerModel('g', 'guest', {'alpha': .9, 'beta': .1}, experience=xp.snapshot(dict(xp.empty('g'), boards=9, stats=stats), 'e3'))
        p = self.make9(gen9={})
        p.meet(seen)
        self.assertGreater(dict(p.opponent.profiles)['beta'], .98)
        self.assertIs(p.opponent, p.opponent_model)
        p.auction_by([seen, 'x', seen, 'x'])
        self.assertGreater(dict(p.bidders[0].profiles)['beta'], .98)
        still = self.make9(gen9=dict(profile_temper=0.))                     # switched off: the declared prior stands
        still.meet(seen)
        self.assertAlmostEqual(dict(still.opponent.profiles)['alpha'], .9)


class OracleTests(Shell):
    def test_refused_without_the_switch(self):
        with patch.dict(os.environ, {'BRIDGE_ALLOW_ORACLE': ''}):
            with self.assertRaises(ValueError):
                self.make9(gen9=dict(oracle=dict(tilt=1.)))
        p = self.make9(gen9={})
        with self.assertRaises(ValueError):
            p.peek([()] * 4)

    def test_tilt_moves_weight_onto_the_true_layout(self):
        with patch.dict(os.environ, {'BRIDGE_ALLOW_ORACLE': '1'}):
            tilted = self.make9(gen9=dict(oracle=dict(tilt=2.)), list_solve=0, list_from_trick=1)
            knows = self.make9(gen9=dict(oracle=dict(tilt='inf')), list_solve=0, list_from_trick=1)
            defence = self.make9(gen9=dict(oracle=dict(tilt=2., roles='defender')), list_solve=0, list_from_trick=1)
        plain = self.make9(gen9={}, list_solve=0, list_from_trick=1)
        listed = 0
        for seed in range(30):
            board, game, before = played(seed, 30)
            o = game.observation()
            view = View(o)
            if len(view.hidden) != 2 or len(o.legal) < 2 or view.count() > 3000:
                continue
            for p in (tilted, knows, defence):
                p.peek(board.hands)
            rng = lambda: np.random.default_rng(seed)
            base_worlds, base_w, _ = plain.layouts(o, view, 'list', rng())
            worlds, w, info = tilted.layouts(o, view, 'list', rng())
            note = info['oracle']
            self.assertTrue(note['present'])                # the list holds every layout
            truth = tuple(tuple(sorted(h)) for h in game.hands)
            i = worlds.index(truth)
            self.assertEqual(list(base_worlds), list(worlds))
            self.assertAlmostEqual(float(np.sum(w)), 1.)
            odds = lambda x: x / (1 - x)
            self.assertAlmostEqual(odds(float(w[i])) / odds(float(base_w[i])), math.exp(2.), places=6)
            self.assertAlmostEqual(note['log_weight_after'] - note['log_weight_before'], math.log(float(w[i]) / float(base_w[i])), places=9)
            only, one_hot, info = knows.layouts(o, view, 'list', rng())
            self.assertEqual(float(one_hot[only.index(truth)]), 1.)
            declaring = o.controller % 2 == o.contract.declarer % 2
            _, w_def, info_def = defence.layouts(o, view, 'list', rng())
            self.assertEqual('oracle' in info_def, not declaring)
            listed += 1
        self.assertGreater(listed, 5)
        with self.assertRaises(RuntimeError):               # shown some other deal
            board, game, _ = played(1, 30)
            other = next(generate(1, 999))
            tilted.peek(other.hands)
            tilted.layouts(game.observation(), View(game.observation()), 'list', np.random.default_rng(0))

    def test_near_moves_the_pool_toward_the_true_layout_without_handing_it_over(self):
        with patch.dict(os.environ, {'BRIDGE_ALLOW_ORACLE': '1'}):
            near = self.make9(gen7=EARLY, gen9=dict(oracle=dict(near=.5)), list_solve=0, list_from_trick=1)
        plain = self.make9(gen7=EARLY, gen9={}, list_solve=0, list_from_trick=1)
        checked = 0
        for seed in range(30):
            board, game, before = played(seed, 30)
            o = game.observation()
            view = View(o)
            if len(view.hidden) != 2 or len(o.legal) < 2 or view.count() > 3000:
                continue
            near.peek(board.hands)
            assign = view.every()
            term = near.play_log_likelihood(o, view, assign) - plain.play_log_likelihood(o, view, assign)
            truth = tuple(tuple(sorted(h)) for h in game.hands)
            rows = [view.world(r) for r in assign]
            i = rows.index(truth)
            self.assertAlmostEqual(float(term[i]), 0., places=9)               # the true layout is at distance 0
            self.assertLess(float(np.delete(term, i).max()), -1e-9)            # every other layout is further
            self.assertGreater(near.near_note['gain'], 0.)
            worlds, w, info = near.layouts(o, view, 'list', np.random.default_rng(seed))
            base_worlds, base_w, _ = plain.layouts(o, view, 'list', np.random.default_rng(seed))
            self.assertEqual(list(worlds), list(base_worlds))                   # same layouts: nothing was added
            self.assertGreater(float(w[worlds.index(truth)]), float(base_w[base_worlds.index(truth)]))
            self.assertIn('oracle_near', info)
            self.assertNotIn('oracle', info)
            checked += 1
        self.assertGreater(checked, 5)

    def test_an_oracle_bot_plays_whole_tables(self):
        with patch.dict(os.environ, {'BRIDGE_ALLOW_ORACLE': '1'}):
            p = self.make9(gen7=EARLY, gen9=dict(oracle=dict(tilt=1.5)), list_solve=16)
        noted = 0
        for seed in (2, 3):
            board = next(generate(1, 700 + seed))
            p.peek(board.hands)
            for a in self.table(p, board, seed % 2)['actions']:
                if a['player'] == 'x' and 'gen6' in a and 'oracle' in a['gen6']:
                    self.assertGreaterEqual(a['gen6']['oracle']['log_weight_after'], a['gen6']['oracle']['log_weight_before'] - 1e-9)
                    noted += 1
        self.assertGreater(noted, 20)


if __name__ == '__main__':
    import unittest
    unittest.main()
