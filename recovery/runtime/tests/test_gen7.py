"""Gen7 prototype: the Gen6 search reading the policy net (bridge_harness/gen7.py, gen7_net.py)."""
import importlib.util
import json
import os
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from bridge_harness.core import Game, card, symbol
from bridge_harness.corpus import generate
from bridge_harness.gen6 import Gen6Player, View
from bridge_harness.gen6_nets import FitScorer, HON_HCP
from bridge_harness.gen7 import Gen7Config, Gen7Player, hidden_plays, past_view, player
from bridge_harness.gen7_net import INPUTS, N_SHOWN, SEAT_SHOWN, Shown, encode, make_bank, stack
from bridge_harness.gen7_tree import Tree, TreeConfig, plain_spots, seat_view
from bridge_harness.players import GreedyPlayer
from bridge_harness.runner import play_table, replay
from test_gen6 import FakeBelief, FakeState, lead_weights, position, scorer_weights

ROOT = Path(__file__).resolve().parents[1]


def trainer():
    spec = importlib.util.spec_from_file_location('train_gen7_policy', ROOT / 'scripts' / 'train_gen7_policy.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def net_weights(path, seed=0, width=32):
    """A random suit net with a small hand bank, in the exported layout."""
    params = trainer().init(1, np.random.default_rng(seed), width)
    length, hon, log_weight = make_bank(256)
    np.savez(path, **params, kind=np.array(1), bank_length=length, bank_hon=hon, bank_log_weight=log_weight)


def played(seed, plies):
    """A random game: the Observation and all four hands before every play, and the position after `plies`."""
    board = next(generate(1, seed))
    game = Game(board)
    rng = random.Random(seed)
    before = []
    for _ in range(plies):
        o = game.observation()
        before.append((o, [tuple(sorted(h)) for h in game.hands]))
        game.play(rng.choice(o.legal))
    return board, game, before


class Fixture(unittest.TestCase):
    """A temporary model folder with random scorer, lead net and policy net; no tests of its own."""

    def setUp(self):
        self.env = patch.dict(os.environ, {'BRIDGE_DDS_CACHE': ''})
        self.env.start()
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        scorer_weights(self.root / 'scorer.npz')
        lead_weights(self.root / 'lead.npz')
        net_weights(self.root / 'gen7.npz')
        for name in ('belief.npz', 'bidder.keras'):
            (self.root / name).write_bytes(b'x')
        self.players = []

    def tearDown(self):
        for p in self.players:
            p.close()
        self.dir.cleanup()
        self.env.stop()

    def make(self, cls=Gen7Player, gen7=None, **switches):
        spec = dict(id='7-test', engine='gen7', samples=8, near_tie=0., exploration=0., scorer='scorer.npz', lead_belief='lead.npz',
                    lead_state_bidder='bidder.keras', belief='belief.npz', belief_kind='public', gen6=switches,
                    gen7_policy='gen7.npz', gen7=gen7 or {})
        with patch('bridge_harness.gen6.BidderState', FakeState), patch('bridge_harness.mixed_arena.Weights', FakeBelief):
            p = cls(spec, self.root)
        self.players.append(p)
        return p


class Gen7Tests(Fixture):
    def listed(self, seed, plies, most=4000, full=False):
        """A position with two hidden hands and a short enough deal list, or None: (Observation, View, views before each play)."""
        board, game, before = played(seed, plies)
        o = game.observation()
        v = View(o)
        if len(v.hidden) != 2 or v.count() > most or len(o.legal) < 2:
            return None
        return (o, v, before, game) if full else (o, v, before)

    # ---- a hidden seat's view ------------------------------------------------------------
    def test_past_view_is_the_observation_that_seat_had(self):
        """Built from the decider's Observation and the seat's cards alone, it equals what the game gave that seat."""
        checked = set()
        for seed in range(30):
            board, game, before = played(seed, 22 + seed % 26)
            o = game.observation()
            for i, seat, chooser in hidden_plays(o):
                true, hands = before[i]
                self.assertEqual(true.controller, chooser)
                self.assertIsNone(o.known_hands[chooser])
                self.assertEqual(past_view(o, i, hands[chooser]), true)
                checked.add((o.controller == o.contract.declarer, seat == o.contract.dummy, i == 0))
        # declarer and defender deciding; cards from dummy and from a hidden hand; the opening lead
        self.assertEqual(checked, {(True, False, False), (True, False, True), (False, False, False), (False, True, False),
                                   (False, False, True)})

    def test_own_plays_are_not_scored_and_the_lead_switch_works(self):
        board, game, _ = played(3, 30)
        o = game.observation()
        c = o.contract
        plays = hidden_plays(o)
        self.assertTrue(all(chooser != o.controller and o.known_hands[chooser] is None for _, _, chooser in plays))
        mine = sum(1 for seat, _ in o.history if (c.declarer if seat == c.dummy else seat) == o.controller)
        self.assertEqual(len(plays) + mine, len(o.history))
        leader_hidden = o.controller != (c.declarer + 1) % 4
        self.assertEqual(len(hidden_plays(o, lead=False)), len(plays) - leader_hidden)

    def test_layout_rows_are_the_encoder_on_that_seats_view(self):
        """The batched inputs for a layout are exactly encode() of the Observation that seat would have had."""
        p = self.make()
        rows = 0
        for seed in range(40):
            spot = self.listed(seed, 24 + seed % 24)
            if spot is None:
                continue
            o, v, _ = spot
            every = v.every()
            pick = every[np.random.default_rng(seed).choice(len(every), min(6, len(every)), replace=False)]
            for i, seat, chooser in hidden_plays(o):
                held = p.held_then(o, v, pick, i, chooser)
                self.assertTrue((held.sum(axis=1) == 13 - sum(s == chooser for s, _ in o.history[:i])).all())
                batch = p.play_arrays(o, i, seat, chooser, held)
                want = stack([p.net.encode(past_view(o, i, [int(x) for x in np.flatnonzero(row)])) for row in held])
                for k in INPUTS:
                    np.testing.assert_array_equal(np.asarray(batch[k]), want[k], err_msg=k)
                self.assertTrue(np.asarray(batch['legal'])[:, o.history[i][1]].all())
                rows += len(held)
        self.assertGreater(rows, 1000)

    def test_true_layout_is_listed_and_scores_what_the_net_gave_each_play(self):
        """For the real deal the likelihood is the sum, over the hidden seats' plays, of the net's (floored) log-probability
        of the card from the Observation that seat really had."""
        p = self.make(gen7=dict(play_floor=.1))
        used = 0
        for seed in range(30):
            spot = self.listed(seed, 28 + seed % 20, full=True)
            if spot is None:
                continue
            o, v, before, game = spot
            every = v.every()
            truth = np.array([[next(j for j, s in enumerate(v.hidden) if int(x) in game.hands[s]) for x in v.unseen]])
            self.assertTrue((every == truth).all(axis=1).any())
            want = 0.
            for i, seat, chooser in hidden_plays(o):
                seen = before[i][0]
                if len(seen.legal) > 1:
                    logp = p.net.log_policy([seen])[0][o.history[i][1]]
                    want += np.log(.9 * np.exp(float(logp)) + .1 / len(seen.legal))
            got = p.play_log_likelihood(o, v, truth)[0]
            self.assertAlmostEqual(got, want, places=4)
            used += 1
        self.assertGreater(used, 8)

    def test_cache_gives_what_a_fresh_player_computes(self):
        a, b = self.make(), self.make()
        checked = 0
        for seed in range(30):
            board, game, _ = played(seed, 30)
            rng = random.Random(seed + 1)
            o1 = game.observation()
            v1 = View(o1)
            if len(v1.hidden) != 2 or v1.count() > 4000:
                continue
            a.play_log_likelihood(o1, v1, v1.every())
            for _ in range(4):
                game.play(rng.choice(game.observation().legal))
            o2 = game.observation()
            v2 = View(o2)
            if o2.controller != o1.controller:
                continue
            before = a.net_rows
            again = a.play_log_likelihood(o2, v2, v2.every())
            reused = a.net_rows - before
            before = b.net_rows
            fresh = b.play_log_likelihood(o2, v2, v2.every())
            np.testing.assert_allclose(again, fresh, atol=1e-5)
            self.assertLess(reused, b.net_rows - before)
            checked += 1
        self.assertGreater(checked, 3)

    # ---- the deal list -------------------------------------------------------------------
    def test_list_weights_are_scorer_weight_times_play_likelihood(self):
        p = self.make(gen7=dict(play_weight=.7), list_solve=0)
        plain = self.make(gen7=dict(play_weight=0.), list_solve=0)
        six = self.make(Gen6Player, list_solve=0)
        used = 0
        for seed in range(30):
            spot = self.listed(seed, 32 + seed % 12, most=600)
            if spot is None:
                continue
            o, v, _ = spot
            worlds, weights, info = p.layouts(o, v, 'list', np.random.default_rng(0))
            every = v.every()
            logw = p.layout_log_weights(o, v, every) + .7 * p.play_log_likelihood(o, v, every)
            w = np.exp(logw - logw.max())
            self.assertEqual(worlds, [v.world(row) for row in every])
            np.testing.assert_allclose(weights, w / w.sum(), atol=1e-9)
            self.assertAlmostEqual(float(weights.sum()), 1.)
            self.assertEqual(info['play_layouts'], len(every))
            self.assertEqual(info['play_decisions'], len(hidden_plays(o)))
            off = plain.layouts(o, v, 'list', np.random.default_rng(0))
            ref = six.layouts(o, v, 'list', np.random.default_rng(0))
            self.assertEqual(off[0], ref[0])
            np.testing.assert_array_equal(off[1], ref[1])
            self.assertNotIn('play_layouts', off[2])
            used += 1
        self.assertGreater(used, 5)

    def test_long_lists_are_cut_by_scorer_weight_before_the_net_scores_them(self):
        p = self.make(gen7=dict(play_max_layouts=50), list_solve=16)
        used = 0
        for seed in range(30):
            spot = self.listed(seed, 30 + seed % 8)
            if spot is None or spot[1].count() <= 50:
                continue
            o, v, _ = spot
            worlds, weights, info = p.layouts(o, v, 'list', np.random.default_rng(1))
            self.assertLessEqual(info['play_layouts'], 50)
            self.assertLessEqual(len(worlds), 16)
            self.assertEqual(len(set(worlds)), len(worlds))
            self.assertAlmostEqual(float(np.sum(weights)), 1.)
            used += 1
        self.assertGreater(used, 3)

    # ---- whole tables --------------------------------------------------------------------
    def table(self, p, board, room, seed=5):
        result = play_table(board, ['x' if s % 2 == room else 'g' for s in range(4)], {'x': p, 'g': GreedyPlayer()}, seed=seed)
        self.assertEqual(result['status'], 'ok', result.get('traceback'))
        replay(dict(board=board.to_dict(), tables=[result]))
        json.dumps(result, allow_nan=False)
        return result

    def test_switches_off_it_plays_gen6s_game_card_for_card(self):
        six = self.make(Gen6Player, list_solve=16)
        seven = self.make(gen7=dict(play_weight=0., tie_break='gen5'), list_solve=16)
        compared = 0
        for seed in (2, 3):
            board = next(generate(1, 700 + seed))
            for room in (0, 1):
                a, b = self.table(six, board, room), self.table(seven, board, room)
                self.assertEqual([x['card'] for x in a['actions']], [x['card'] for x in b['actions']])
                for x, y in zip(a['actions'], b['actions']):
                    if x['player'] == 'x' and 'gen6' in x:
                        self.assertEqual(x['estimates'], y['estimates'])
                        self.assertEqual(x['behavior_probabilities'], y['behavior_probabilities'])
                        self.assertEqual({k: v for k, v in x['gen6'].items() if not k.endswith('seconds')},
                                         {k: v for k, v in y['gen6'].items() if not k.endswith('seconds')})
                        self.assertEqual(y['gen7'], dict(Gen7Config(play_weight=0., tie_break='gen5').__dict__))
                        compared += 1
        self.assertGreater(compared, 40)

    def test_full_tables_with_everything_on(self):
        p = self.make(list_solve=16, list_from_trick=5)
        with_play = 0
        for seed in (2, 3):
            board = next(generate(1, 700 + seed))
            for room in (0, 1):
                for a in self.table(p, board, room)['actions']:
                    if a['player'] != 'x' or 'gen6' not in a:
                        continue
                    self.assertLessEqual(a['selected_pimc_gap'], 1e-9)
                    if a['gen6']['source'] == 'deal_list':
                        self.assertGreater(a['gen6']['play_decisions'], 0)
                        self.assertGreaterEqual(a['gen6']['effective'] + 1e-9, 1.)
                        with_play += 1
                    else:
                        self.assertNotIn('play_decisions', a['gen6'])
        self.assertGreater(with_play, 10)

    def test_early_tricks_from_the_net_carry_no_search_estimates(self):
        for sample in (False, True):
            p = self.make(gen7=dict(search_from_trick=3, net_sample=sample), list_solve=16)
            unsearched = searched = 0
            board = next(generate(1, 702))
            for room in (0, 1):
                for a in self.table(p, board, room)['actions']:
                    if a['player'] != 'x' or a.get('forced'):
                        continue
                    if a['ply'] < 8:
                        self.assertTrue(a['unsearched'])
                        self.assertNotIn('estimates', a)
                        self.assertNotIn('gen6', a)
                        self.assertEqual(a['gen7']['source'], 'net')
                        self.assertAlmostEqual(sum(a['net_probabilities'].values()), 1., places=5)
                        self.assertGreater(a['behavior_probabilities'][a['card']], 0.)
                        unsearched += 1
                    else:
                        self.assertIn('estimates', a)
                        searched += 1
            self.assertGreater(unsearched, 3)
            self.assertGreater(searched, 15)

    # ---- ties ----------------------------------------------------------------------------
    def test_ties_go_to_the_nets_most_probable_card(self):
        p = self.make(list_solve=0)
        old = self.make(gen7=dict(tie_break='gen5'), list_solve=0)
        used = 0
        for seed in range(40):
            spot = self.listed(seed, 34 + seed % 10, most=300)
            if spot is None:
                continue
            o, v, _ = spot
            worlds, weights, _ = p.layouts(o, v, 'list', np.random.default_rng(0))
            stats = p.dds.cache_stats()
            solved = p.dds.solve_batch(worlds, o.contract.trump, o.leader, o.trick, fixed_seats=[s for s, h in enumerate(o.known_hands) if h is not None])
            search = p.search_decision(o, random.Random(seed), solved, weights, stats, p.dds.cache_stats(), dict(source='test'))
            eligible = [card(k) for k, q in search.details['behavior_probabilities'].items() if q > 0]
            got = p.break_ties(o, random.Random(seed), search)
            self.assertIs(old.break_ties(o, random.Random(seed), search), search)        # no Gen5 net in this spec
            if len(eligible) < 2:
                self.assertIs(got, search)
                continue
            logp = p.net.log_policy([o])[0]
            self.assertEqual(got.card, max(eligible, key=lambda x: logp[x]))
            self.assertEqual(got.details['proposal_probabilities'], search.details['behavior_probabilities'])
            self.assertEqual(set(got.details['selector_predictions']), set(k for k, q in search.details['behavior_probabilities'].items() if q > 0))
            self.assertEqual(got.details['selected_probability'], 1.)
            self.assertLessEqual(got.details['selected_pimc_gap'], 1e-9)
            used += 1
        self.assertGreater(used, 5)

    def test_factory(self):
        with patch('bridge_harness.gen6.BidderState', FakeState), patch('bridge_harness.mixed_arena.Weights', FakeBelief):
            base = dict(samples=8, near_tie=0., scorer='scorer.npz', lead_belief='lead.npz', lead_state_bidder='bidder.keras')
            a = player(dict(base, id='7', engine='gen7', gen7_policy='gen7.npz'), self.root)
            b = player(dict(base, id='6', engine='gen6'), self.root)
        self.players += [a, b]
        self.assertIs(type(a), Gen7Player)
        self.assertIs(type(b), Gen6Player)
        with self.assertRaises(ValueError):
            Gen7Config(tie_break='coin')


class TreeTests(Fixture):
    """The tree search (bridge_harness/gen7_tree.py)."""

    def spot(self, seed, plies, most=400):
        """A position after the lead with a short deal list: (player, Observation, layouts, weights, game, views before each play)."""
        p = self.make(list_solve=0)
        board, game, before = played(seed, plies)
        o = game.observation()
        v = View(o)
        if len(v.hidden) != 2 or v.count() > most or len(o.legal) < 2:
            return None
        worlds, weights, _ = p.layouts(o, v, 'list', np.random.default_rng(0))
        return p, o, worlds, weights, game, before

    def test_seat_view_is_the_observation_that_seat_had(self):
        checked = 0
        for seed in range(12):
            board, game, before = played(seed, 30 + seed)
            o = game.observation()
            dummy = o.contract.dummy
            for i in range(1, len(before)):
                true, hands = before[i]
                self.assertEqual(seat_view(o, o.history[:i], hands[dummy], true.controller, true.actor, hands[true.controller]), true)
                self.assertEqual(seat_view(o, o.history[:i], hands[dummy], true.controller, true.actor, hands[true.controller], true.declarer_tricks), true)
                checked += 1
        self.assertGreater(checked, 300)

    def test_no_tricks_is_pimc(self):
        used = 0
        for seed in range(30):
            got = self.spot(seed, 30 + seed % 14)
            if got is None:
                continue
            p, o, worlds, weights, _, _ = got
            solved = p.dds.solve_batch(worlds, o.contract.trump, o.leader, o.trick, fixed_seats=[s for s, h in enumerate(o.known_hands) if h is not None])
            stats = p.dds.cache_stats()
            want = p.search_decision(o, random.Random(0), solved, weights, stats, stats, {}).details['estimates']
            tree = Tree(p.net, p.dds, TreeConfig(tricks=0))
            for x, value in tree.values(o, worlds, weights).items():
                self.assertAlmostEqual(value, want[symbol(x)]['utility'], places=9)
            self.assertEqual(tree.net_rows, 0)
            used += 1
        self.assertGreater(used, 6)

    def test_reply_rows_are_the_encoder_on_that_seats_view_in_each_layout(self):
        rows = 0
        for seed in range(30):
            got = self.spot(seed, 26 + seed % 16)
            if got is None:
                continue
            p, o, worlds, weights, game, _ = got
            tree = Tree(p.net, p.dds, TreeConfig(tricks=2))
            tree.values(o, worlds, weights, cards=[])                    # sets the search up; no card is searched
            c = o.contract
            history, tricks, gone = tuple(o.history), o.declarer_tricks, np.zeros(52, bool)
            rng = random.Random(seed)
            for _ in range(6):                                           # walk the real game on from here
                if game.done:
                    break
                now = game.observation()
                if now.controller != o.controller:
                    live = np.arange(len(worlds))
                    held = tree.member[:, now.actor] & ~gone
                    led = now.trick[0][1] // 13 if now.trick else None
                    in_suit = held & (np.arange(52) // 13 == led) if now.trick else held
                    legal = np.where(in_suit.any(axis=1)[:, None], in_suit, held)
                    batch = tree.reply_inputs(history, tricks, gone, now.actor, now.controller, live, legal)
                    dummy_hand = [x for x in o.known_hands[c.dummy] if not gone[x]]
                    want = stack([p.net.encode(seat_view(o, history, dummy_hand, now.controller, now.actor,
                                                         [x for x in w[now.controller] if not gone[x]])) for w in worlds])
                    for k in INPUTS:
                        np.testing.assert_array_equal(np.asarray(batch[k]), want[k], err_msg=k)
                    rows += len(worlds)
                x = rng.choice(now.legal)
                game.play(x)
                history += ((now.actor, x),)
                gone[x] = True
                tricks = game.declarer_tricks
                # keep only layouts in which that card was that seat's to play
                keep = [i for i, w in enumerate(worlds) if x in w[now.actor]]
                if len(keep) < len(worlds):
                    worlds = [worlds[i] for i in keep]
                    tree.member = tree.member[keep]
                if not worlds:
                    break
        self.assertGreater(rows, 200)

    def test_probability_of_the_play_is_carried_whole(self):
        """With every card kept, the layouts' weights reach the leaves undiminished."""
        class Count(Tree):
            def leaf(self, history, trick, declarer_tricks, gone, reach):
                self.lines += 1
                return float(reach.sum())
        used = 0
        for seed in range(30):
            got = self.spot(seed, 28 + seed % 12, most=60)
            if got is None:
                continue
            p, o, worlds, weights, _, _ = got
            for breadth, mass in ((13, 1.), (2, .9)):
                tree = Count(p.net, p.dds, TreeConfig(tricks=2, breadth=breadth, mass=mass))
                for value in tree.values(o, worlds, weights).values():
                    self.assertAlmostEqual(value, 1., places=9)
            used += 1
        self.assertGreater(used, 4)

    def test_the_deciders_later_card_is_one_choice_for_all_layouts(self):
        """At the decider's own later turn the value is the best single card's average, never each layout's own best."""
        used = fused_would_differ = 0
        for seed in range(60):
            got = self.spot(seed, 24 + seed % 20)
            if got is None:
                continue
            p, o, worlds, weights, game, _ = got
            c = o.contract
            if game.done or len(worlds) < 2:
                continue
            tree = Tree(p.net, p.dds, TreeConfig(tricks=2, breadth=3, mass=1.))
            tree.values(o, worlds, weights, cards=[])
            payoff = np.random.default_rng(seed).random((len(worlds), 52))
            seen = []

            def after(history, declarer_tricks, gone, tricks_done, seat, x, reach):
                seen.append(x)
                return float((reach * payoff[:, x]).sum())
            tree.after = after
            reach = np.asarray(weights, float) / float(np.sum(weights))
            value = tree.node(tuple(o.history), o.declarer_tricks, np.zeros(52, bool), 0, reach)     # the decider is to play now
            self.assertTrue(set(seen) <= set(o.legal))
            self.assertLessEqual(len(seen), 3)
            self.assertAlmostEqual(value, max(float((reach * payoff[:, x]).sum()) for x in seen), places=12)
            fused = float((reach * payoff[:, seen].max(axis=1)).sum())
            self.assertLessEqual(value, fused + 1e-12)
            fused_would_differ += fused > value + 1e-6
            used += 1
        self.assertGreater(used, 8)
        self.assertGreater(fused_would_differ, 4)

    def test_double_dummy_replies_with_honest_own_cards_never_beat_pimc(self):
        used = 0
        for seed in range(40):
            got = self.spot(seed, 26 + seed % 12, most=200)
            if got is None:
                continue
            p, o, worlds, weights, _, _ = got
            index = np.argsort(-np.asarray(weights))[:6]
            sub, share = [worlds[i] for i in index], [weights[i] for i in index]
            pimc = Tree(p.net, p.dds, TreeConfig(tricks=0)).values(o, sub, share)
            honest = Tree(p.net, p.dds, TreeConfig(tricks=2, reply='dd', own_breadth=13)).values(o, sub, share)
            for x in o.legal:
                self.assertLessEqual(honest[x], pimc[x] + 1e-9)
            used += 1
            if used >= 6:
                break
        self.assertGreaterEqual(used, 6)

    def test_the_deciders_later_card_from_the_net_or_a_search_is_an_average_not_the_best(self):
        """own='net' and own='search' treat the decider's later self like any other seat: a weighted mean over its cards."""
        used = below_best = 0
        for seed in range(60):
            got = self.spot(seed, 24 + seed % 20)
            if got is None:
                continue
            p, o, worlds, weights, game, _ = got
            if game.done or len(worlds) < 2:
                continue
            payoff = np.random.default_rng(seed).random((len(worlds), 52))
            reach = np.asarray(weights, float) / float(np.sum(weights))
            worth = lambda x: float((reach * payoff[:, x]).sum())
            asked = []

            def replier(view):
                asked.append(view)
                first, second = view.legal[0], view.legal[1]
                return {first: .75, second: .25}
            for own in ('net', 'search'):
                tree = Tree(p.net, p.dds, TreeConfig(tricks=2, breadth=2, mass=1., own=own), replier=replier)
                tree.values(o, worlds, weights, cards=[])
                seen = []

                def after(history, declarer_tricks, gone, tricks_done, seat, x, reach):
                    seen.append(x)
                    return float((reach * payoff[:, x]).sum())
                tree.after = after
                value = tree.node(tuple(o.history), o.declarer_tricks, np.zeros(52, bool), 0, reach)
                self.assertEqual(len(seen), 2)
                if own == 'search':
                    self.assertEqual(asked[-1], o)                     # asked with the decider's own view, nothing more
                    self.assertAlmostEqual(value, .75 * worth(o.legal[0]) + .25 * worth(o.legal[1]), places=12)
                else:
                    q = np.exp(p.net.log_policy([o])[0][seen].astype(np.float64))
                    self.assertAlmostEqual(value, float(q @ [worth(x) for x in seen] / q.sum()), places=9)
                self.assertLessEqual(value, max(worth(x) for x in seen) + 1e-12)
                below_best += value < max(worth(x) for x in seen) - 1e-6
            used += 1
        self.assertGreater(used, 8)
        self.assertGreater(below_best, 8)

    def test_search_replies_ask_from_that_seats_view_and_carry_the_probability_whole(self):
        class Count(Tree):
            def leaf(self, history, trick, declarer_tricks, gone, reach):
                self.lines += 1
                return float(reach.sum())
        used = asked_total = 0
        for seed in range(30):
            got = self.spot(seed, 28 + seed % 12, most=60)
            if got is None:
                continue
            p, o, worlds, weights, _, _ = got
            asked = []

            def replier(view):
                asked.append(view)
                return {x: 1. / len(view.legal) for x in view.legal}
            tree = Count(p.net, p.dds, TreeConfig(tricks=2, breadth=13, reply='search', own='search'), replier=replier)
            for value in tree.values(o, worlds, weights).values():
                self.assertAlmostEqual(value, 1., places=9)
            self.assertEqual(tree.replies, len(asked))
            self.assertEqual(tree.net_rows, 0)
            dummy = o.contract.dummy
            for view in asked:
                seats = [s for s, h in enumerate(view.known_hands) if h is not None]
                self.assertEqual(sorted(seats), sorted({view.controller, dummy}))          # its own hand and dummy, nothing else
                gone = {x for _, x in view.history}
                self.assertTrue(any(set(view.known_hands[view.controller]) == set(w[view.controller]) - gone for w in worlds))
            asked_total += len(asked)
            used += 1
        self.assertGreater(used, 4)
        self.assertGreater(asked_total, 50)

    def test_two_trick_trees_play_legal_lines_to_a_sane_value(self):
        used = 0
        for seed in range(40):
            got = self.spot(seed, 26 + seed % 12, most=200)
            if got is None:
                continue
            p, o, worlds, weights, _, _ = got
            index = np.argsort(-np.asarray(weights))[:6]
            tree = Tree(p.net, p.dds, TreeConfig(tricks=2, breadth=2, mass=.9, layouts=6))
            values = tree.values(o, [worlds[i] for i in index], [weights[i] for i in index])     # DDS rejects any illegal position
            self.assertEqual(set(values), set(o.legal))
            self.assertTrue(all(-13 <= v <= 13 for v in values.values()))
            self.assertGreater(tree.lines, len(o.legal))
            with self.assertRaises(ValueError):
                Tree(p.net, p.dds, TreeConfig()).values(played(seed, 0)[1].observation(), worlds, weights)      # the opening lead
            used += 1
            if used >= 5:
                break
        self.assertGreaterEqual(used, 5)
        with self.assertRaises(ValueError):
            TreeConfig(mass=0.)


    def test_plain_spots_keeps_honours_and_lengths_and_deals_low_cards_in_turn(self):
        used = 0
        for seed in range(30):
            got = self.spot(seed, 26 + seed % 12, most=200)
            if got is None:
                continue
            p, o, worlds, weights, _, _ = got
            hidden = [s for s, h in enumerate(o.known_hands) if h is None]
            new, share = plain_spots(worlds, weights, hidden)
            self.assertAlmostEqual(sum(share), float(np.sum(weights)), places=9)
            self.assertLessEqual(len(new), len(worlds))
            self.assertEqual(len(set(new)), len(new))
            shape = lambda w: tuple((tuple(sum(c // 13 == s for c in w[seat]) for s in range(4)), tuple(sorted(c for c in w[seat] if c % 13 >= 8)))
                                    for seat in hidden)
            self.assertEqual({shape(w) for w in new}, {shape(w) for w in worlds})        # same honours and lengths, layout by layout
            for w in new:
                self.assertEqual(sorted(c for h in w for c in h), sorted(c for h in worlds[0] for c in h))
                for seat in range(4):
                    if seat not in hidden:
                        self.assertEqual(w[seat], worlds[0][seat])
                for suit in range(4):
                    lows = [[c for c in w[seat] if c // 13 == suit and c % 13 < 8] for seat in hidden]
                    pool = sorted(lows[0] + lows[1])
                    if lows[0]:
                        self.assertEqual(lows[0][0], pool[0])                            # the first hidden hand holds the lowest
                    if lows[0] and lows[1]:
                        self.assertEqual(lows[1][0], pool[1])                            # and the second the next
            tree = Tree(p.net, p.dds, TreeConfig(tricks=0, plain=1))
            again = Tree(p.net, p.dds, TreeConfig(tricks=0))
            for x, value in tree.values(o, worlds, weights).items():                     # no tricks: plain search on the re-dealt layouts
                self.assertAlmostEqual(value, again.values(o, new, share)[x], places=9)
            used += 1
            if used >= 6:
                break
        self.assertGreaterEqual(used, 6)

    def test_cards_that_do_the_same_job_are_one_card(self):
        p = self.make(list_solve=0)
        _, game, _ = played(3, 30)
        tree = Tree(p.net, p.dds, TreeConfig(plain=1))
        tree.o = game.observation()
        trump = tree.o.contract.trump
        suit = next(s for s in range(4) if s != trump)
        c = lambda rank: 13 * suit + '23456789TJQKA'.index(rank)
        held, gone = np.zeros(52, bool), np.zeros(52, bool)
        held[[c('2'), c('5'), c('6'), c('9'), c('Q'), c('K')]] = True
        self.assertEqual(tree.plain(c('K'), held, (), 0, gone), c('Q'))                  # touching honours: the lower
        self.assertEqual(tree.plain(c('6'), held, (), 0, gone), c('2'))                  # a low card led: the lowest
        gone[[c('7'), c('8')]] = True
        lead = ((3, c('7')),)
        self.assertEqual(tree.plain(c('5'), held, lead, 0, gone), c('2'))                # follows without taking the trick: the lowest
        self.assertEqual(tree.plain(c('9'), held, lead, 0, gone), c('9'))                # takes it: the cheapest low card that does
        gone[c('8')] = False
        gone[c('4')] = True
        self.assertEqual(tree.plain(c('6'), held, ((3, c('4')),), 0, gone), c('5'))      # 5 and 6 both take the 4: the 5
        held[c('A')] = True
        self.assertEqual(tree.plain(c('A'), held, (), 0, gone), c('Q'))                  # A K Q in one hand
        held[c('K')] = False
        self.assertEqual(tree.plain(c('A'), held, (), 0, gone), c('A'))                  # the king is out: the ace is its own card
        gone[c('K')] = True
        self.assertEqual(tree.plain(c('A'), held, (), 0, gone), c('Q'))                  # the king has gone: touching again
        cards, mass = tree.same_job(np.array([c('2'), c('5'), c('Q'), c('A')]), np.array([.1, .2, .3, .4]), held, (), 0, gone)
        self.assertEqual(dict(zip(cards.tolist(), np.round(mass, 9).tolist())), {c('2'): .3, c('Q'): .7})
        off = Tree(p.net, p.dds, TreeConfig())
        cards, mass = off.same_job(np.array([c('2'), c('5')]), np.array([.4, .6]), held, (), 0, gone)
        self.assertEqual(cards.tolist(), [c('2'), c('5')])

    def test_plain_trees_carry_the_probability_whole_and_play_legal_lines(self):
        class Count(Tree):
            def leaf(self, history, trick, declarer_tricks, gone, reach):
                self.lines += 1
                return float(reach.sum())
        used = fewer = 0
        for seed in range(40):
            got = self.spot(seed, 26 + seed % 12, most=200)
            if got is None:
                continue
            p, o, worlds, weights, _, _ = got
            index = np.argsort(-np.asarray(weights))[:6]
            sub, share = [worlds[i] for i in index], [weights[i] for i in index]
            for reply in ('net', 'dd'):
                counted = Count(p.net, p.dds, TreeConfig(tricks=2, breadth=13, mass=1., reply=reply, plain=1))
                for value in counted.values(o, sub, share).values():
                    self.assertAlmostEqual(value, 1., places=9)
            exact = Tree(p.net, p.dds, TreeConfig(tricks=2, layouts=6))
            plain = Tree(p.net, p.dds, TreeConfig(tricks=2, layouts=6, plain=1))
            exact.values(o, sub, share)
            values = plain.values(o, sub, share)                                         # DDS rejects any illegal position
            self.assertEqual(set(values), set(o.legal))
            self.assertTrue(all(-13 <= v <= 13 for v in values.values()))
            fewer += plain.lines < exact.lines
            used += 1
            if used >= 5:
                break
        self.assertGreaterEqual(used, 5)
        self.assertGreaterEqual(fewer, 3)

    def test_stake_rule_runs_from_the_uniform_tree_to_pimc(self):
        """With no threshold to speak of the stake rule cuts nothing; with a huge one every root card is a leaf."""
        used = 0
        for seed in range(40):
            got = self.spot(seed, 26 + seed % 12, most=200)
            if got is None:
                continue
            p, o, worlds, weights, _, _ = got
            index = np.argsort(-np.asarray(weights))[:6]
            sub, share = [worlds[i] for i in index], [weights[i] for i in index]
            for plain in (0, 1):
                uniform = Tree(p.net, p.dds, TreeConfig(tricks=2, layouts=6, plain=plain))
                want = uniform.values(o, sub, share)
                wide = Tree(p.net, p.dds, TreeConfig(tricks=2, layouts=6, plain=plain, path=1e-30))
                self.assertEqual(wide.values(o, sub, share), want)
                self.assertEqual(wide.lines, uniform.lines)
                pimc = Tree(p.net, p.dds, TreeConfig(tricks=0, plain=plain)).values(o, sub, share)
                shut = Tree(p.net, p.dds, TreeConfig(tricks=2, layouts=6, plain=plain, path=1e9))
                got_values = shut.values(o, sub, share)
                for x in o.legal:
                    self.assertAlmostEqual(got_values[x], pimc[x], places=9)
                    self.assertAlmostEqual(shut.flat[x], pimc[x], places=9)          # the tree's own double-dummy values
                self.assertEqual(shut.net_rows, 0)
                self.assertEqual(shut.lines, len(o.legal))
                self.assertGreaterEqual(wide.stake, 0.)
                lines = []
                for path in (.05, .5, 5.):                                          # a higher threshold never searches more
                    tree = Tree(p.net, p.dds, TreeConfig(tricks=3, breadth=3, mass=.98, layouts=6, plain=plain, path=path))
                    values = tree.values(o, sub, share)
                    self.assertEqual(set(values), set(o.legal))
                    self.assertTrue(all(-13 <= v <= 13 for v in values.values()))
                    lines.append(tree.lines)
                self.assertEqual(lines, sorted(lines, reverse=True))
                capped = Tree(p.net, p.dds, TreeConfig(tricks=3, breadth=3, mass=.98, layouts=6, plain=plain, path=.05, path_solves=12))
                capped.values(o, sub, share)
                self.assertLessEqual(capped.lines, lines[0])
                handed = Tree(p.net, p.dds, TreeConfig(tricks=2, layouts=6, plain=plain, path=1.))
                handed.values(o, sub, share, stake=1e12)                            # a stake handed in replaces the tree's own
                self.assertEqual(handed.lines, uniform.lines)
            used += 1
            if used >= 4:
                break
        self.assertGreaterEqual(used, 4)
        for bad in (dict(path=-1.), dict(spread=-1.), dict(path_solves=-1), dict(path_solves=1.5)):
            with self.assertRaises(ValueError):
                TreeConfig(**bad)

    def test_the_stake_is_the_imps_of_the_trick_at_risk(self):
        from types import SimpleNamespace
        from bridge_harness.core import Contract
        tree = Tree(None, None, TreeConfig(path=1.))
        tree.o = SimpleNamespace(contract=Contract(4, 'S', 0), vulnerability='Both')
        tree.declaring = True
        self.assertEqual([tree.swing(t) for t in (9, 10, 11)], [3, 12, 1])       # one more down; the game; an overtrick
        tree.declaring = False
        self.assertEqual([tree.swing(t) for t in (8, 9, 10)], [3, 12, 1])        # the trick a defender would give away
        self.assertEqual(tree.swing(13), tree.swing(12))
        reach = np.array([.5, .25, .25, 0.])
        self.assertAlmostEqual(tree.stake_of([9, 9, 10], reach), .75 * 12 + .25 * 1)
        wary = Tree(None, None, TreeConfig(path=1., spread=1.))
        wary.o, wary.declaring = tree.o, False
        self.assertAlmostEqual(wary.stake_of([9, 9, 10], reach), 9.25 + float(np.sqrt(.75 * 2.75 ** 2 + .25 * 8.25 ** 2)))


class ShownTests(unittest.TestCase):
    """What the calls show: the scorer's posterior over a reweighted bank of random hands."""

    def test_bank_reweighted_is_plain_dealing(self):
        length, hon, log_weight = make_bank(4096)
        w = np.exp(log_weight.astype(np.float64))
        w /= w.sum()
        points = HON_HCP[hon.astype(np.int64)].sum(axis=1)
        self.assertTrue((length.sum(axis=1) == 13).all())
        self.assertAlmostEqual(float(w @ points), 10., delta=.25)
        self.assertAlmostEqual(float(w @ (points >= 16)), .098, delta=.012)
        self.assertAlmostEqual(float(w @ (length.max(axis=1) >= 6)), .2075, delta=.02)
        np.testing.assert_allclose(w @ length, [3.25] * 4, atol=.08)
        ordinary = (points < 16) & (length.max(axis=1) < 6)
        self.assertGreater(float(np.exp(log_weight[ordinary]).min()), 1.)           # ordinary hands are under-drawn, by a fifth
        self.assertAlmostEqual(float(np.exp(-log_weight[ordinary]).mean()), .8, delta=.01)
        self.assertLess(float(np.exp(-log_weight).max()), 3.)                       # nothing more than three times as common as dealt

    def test_view_is_in_the_controllers_seat_order_and_needs_only_the_observation(self):
        with tempfile.TemporaryDirectory() as d:
            scorer_weights(Path(d) / 's.npz')
            shown = Shown(FitScorer(Path(d) / 's.npz'), *make_bank(256))
            board, game, _ = played(5, 9)
            o = game.observation()
            rows = shown.seats(o.auction, o.dealer, o.vulnerability)
            self.assertEqual(rows.shape, (4, SEAT_SHOWN))
            x = encode(o, shown)['shown']
            self.assertEqual(x.shape, (N_SHOWN,))
            for r in range(4):
                np.testing.assert_array_equal(x[r * SEAT_SHOWN:(r + 1) * SEAT_SHOWN], rows[(o.controller + r) % 4])
            self.assertTrue((encode(o)['shown'] == 0).all())
            self.assertTrue(np.isfinite(rows).all())
            np.testing.assert_allclose(rows[:, :4].sum(axis=1) * 5, 13., atol=1e-4)      # expected lengths add to thirteen


if __name__ == '__main__':
    unittest.main()
