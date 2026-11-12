"""Plan research: honest playouts (bridge_harness/plan_rollout.py), layout families and the plan player."""
import random
import unittest

import numpy as np

from bridge_harness.core import Game
from bridge_harness.gen6 import Classes, View
from bridge_harness.gen7 import utilities
from bridge_harness.gen7_net import INPUTS
from bridge_harness.plan_families import Features, held_out, key_variables
from bridge_harness.plan_player import PlanPlayer, PlayoutUse, playout_stages
from bridge_harness.plan_rollout import Believer, NetPlayer, Public, Rows, card_values, inputs, play_out, solve_rows
from test_gen7 import Fixture, played


def spot(seed, plies):
    """A random game after `plies` cards: (game, Observation, the four hands as they stand)."""
    board, game, _ = played(seed, plies)
    return game, game.observation(), tuple(tuple(sorted(h)) for h in game.hands)


class RolloutTests(Fixture):
    def test_batched_inputs_are_the_encoder_on_each_seats_view(self):
        """Along a random continuation, every row's inputs equal gen7_net.encode of the Observation the game gives."""
        p = self.make()
        checked = set()
        for seed in range(12):
            game, o, world = spot(seed, 1 + 3 * seed)
            rows, public, rng = Rows(o, [world, world]), Public(p.net, o), random.Random(seed)
            while not game.done:
                now = game.observation()
                want, got = p.net.encode(now), inputs(rows, public)
                for k in INPUTS:
                    np.testing.assert_array_equal(np.asarray(want[k], np.float32), np.asarray(got[k][0], np.float32), err_msg=f'{k} seed {seed}')
                    np.testing.assert_array_equal(got[k][0], got[k][1])
                checked.add((now.controller == now.contract.declarer, now.actor == now.contract.dummy, len(now.trick)))
                x = rng.choice(now.legal)
                game.play(x)
                rows.play([x, x])
            self.assertTrue(rows.done)
            self.assertEqual(int(rows.won[0]), game.declarer_tricks)
        self.assertEqual(len(checked), 12)      # declarer's own card, dummy's card and a defender's, at each position in a trick

    def test_rows_refuse_a_layout_that_does_not_fit_the_play(self):
        game, o, world = spot(3, 9)
        bad = list(world)
        bad[0] = bad[0] + (o.history[0][1],)
        with self.assertRaises(ValueError):
            Rows(o, [tuple(bad)])

    def test_show_outs_are_tracked(self):
        for seed in range(6):
            board, game, before = played(seed, 40)
            o = game.observation()
            rows = Rows(before[1][0], [tuple(before[1][1])])
            want = np.zeros((4, 4), bool)
            for i, (seat, x) in enumerate(o.history):
                led = o.history[i - i % 4][1] // 13
                if x // 13 != led:
                    want[seat, led] = True
            for seat, x in o.history[1:]:
                rows.play([x])
            np.testing.assert_array_equal(rows.void[0], want)
            np.testing.assert_array_equal(Rows(o, [tuple(tuple(sorted(h)) for h in game.hands)]).void[0], want)

    def test_net_playouts_are_legal_games(self):
        """Each row is a legal game from the layout it was given, and its count of tricks is the game's."""
        p = self.make()
        for seed, mode in ((1, 'top'), (2, 'draw'), (3, 'blend')):
            game, o, world = spot(seed, 6)
            who = NetPlayer(p.net, mode, seed=seed)
            rows, public = Rows(o, [world] * 3), Public(p.net, o)
            games = [Game(game.board) for _ in range(3)]
            for g in games:
                for _, x in o.history:
                    g.play(x)
            while not rows.done:
                cards = who.cards(rows, public)
                for g, x in zip(games, cards):
                    self.assertIn(int(x), g.observation().legal)
                    g.play(int(x))
                rows.play(cards)
            self.assertEqual([int(x) for x in rows.won], [g.declarer_tricks for g in games])

    def test_solved_rows_are_the_solvers_values(self):
        p = self.make()
        for seed in range(4):
            game, o, world = spot(seed, 8 + 4 * seed)
            rows = Rows(o, [world])
            (values, _), = p.dds.solve_batch([world], o.contract.trump, o.leader, ())
            declaring = o.leader % 2 == o.contract.declarer % 2
            remaining = 13 - len(o.history) // 4
            want = o.declarer_tricks + (max(values.values()) if declaring else remaining - max(values.values()))
            self.assertEqual(int(solve_rows(rows, p.dds)[0]), want)

    def test_a_horizon_of_one_trick_then_the_solver(self):
        """Stopping after the trick in progress and solving from there gives the solver's value of whatever was played."""
        p = self.make()
        game, o, world = spot(5, 9)
        x = o.legal[0]
        rows, public = Rows(o, [world]), Public(p.net, o)
        rows.play([x])
        got = play_out(rows.copy(), NetPlayer(p.net, 'top'), public, tricks=1, dds=p.dds)
        check = rows.copy()
        while check.played % 4:
            check.play(NetPlayer(p.net, 'top').cards(check, public))
        self.assertEqual(int(got[0]), int(solve_rows(check, p.dds)[0]))

    def test_believers_who_know_the_layout_play_double_dummy(self):
        """If every seat's believed layout is the real one, both sides play the solver's cards and the playout takes
        exactly the double-dummy tricks of each first card."""
        p = self.make()

        class Knows(Believer):
            def believed(self, lean, held, cap, void_a, void_b, draw):
                return self.first

        for seed in range(5):
            game, o, world = spot(seed, 13 + 4 * seed)
            (values, _), = p.dds.solve_batch([world], o.contract.trump, o.leader, o.trick)
            want = utilities(o, values)
            who = Knows(p.net, p.dds)
            for x in o.legal:
                rows = Rows(o, [world])
                rows.play([x])
                public = Public(p.net, o)
                while not rows.done:        # hand the seat the real cards of the first hand it cannot see
                    k = int(rows.controller()[0])
                    a = [s for s in range(4) if s != k and s != rows.dummy][0]
                    who.first = np.flatnonzero(rows.holder[0] == a)
                    rows.play(who.cards(rows, public))
                won = int(rows.won[0])
                declaring = o.controller % 2 == o.contract.declarer % 2
                self.assertEqual(won if declaring else -won, want[x], f'seed {seed} card {x}')

    def test_believed_layouts_fit_what_the_seat_can_know(self):
        """The believed hand has the right number of cards, only unseen ones, and none of a suit its holder has shown out of."""
        p = self.make()
        who = Believer(p.net, p.dds, 'draw', seed=1)
        rng = np.random.default_rng(0)
        for _ in range(50):
            held = rng.random(52) < .5
            cap = int(rng.integers(0, held.sum() + 1))
            void_a = np.zeros(4, bool)
            void_b = np.zeros(4, bool)
            suit_counts = [int(held[13 * s:13 * s + 13].sum()) for s in range(4)]
            s = int(rng.integers(4))
            if held.sum() - suit_counts[s] >= cap:
                void_a[s] = True
            first = who.believed(rng.normal(size=52), held, cap, void_a, void_b, True)
            self.assertEqual(len(first), cap)
            self.assertTrue(held[first].all())
            self.assertFalse((first // 13 == s).any() and void_a[s])

    def test_card_values_count_as_the_search_does(self):
        """Declarer's side gets its tricks, the defence minus declarer's: the units of PIMC's estimates."""
        p = self.make()
        seen = set()
        for seed in range(8):
            game, o, world = spot(seed, 5 + seed)
            v = card_values(o, [world, world], list(o.legal)[:2], NetPlayer(p.net, 'top'))
            declaring = o.controller % 2 == o.contract.declarer % 2
            self.assertTrue((v >= 0).all() if declaring else (v <= 0).all())
            np.testing.assert_array_equal(v[0], v[1])
            seen.add(declaring)
        self.assertEqual(seen, {True, False})


class FamilyTests(Fixture):
    def test_key_variables_find_what_the_outcome_depends_on(self):
        rng = np.random.default_rng(0)
        x = rng.integers(0, 2, (400, 12))
        y = x[:, 3] + .5 * (x[:, 7] & x[:, 3]) + .05 * rng.normal(size=400)
        key = key_variables(x, y, np.ones(400))
        self.assertEqual(key.variables[:2], [3, 7])
        self.assertGreater(key.explained[1], .95)
        self.assertGreater(held_out(x, y, np.ones(400))[2], .95)
        self.assertEqual(sorted(set(key.families(x, 2))), [0, 1, 2, 3])
        self.assertEqual(key_variables(x, np.zeros(400), np.ones(400)).variables, [])

    def test_class_answers_agree_with_layout_answers(self):
        """A variable's answer for a hand-type class is its answer for every layout dealt from that class."""
        p = self.make()
        for seed in range(6):
            game, o, world = spot(seed, 6 + 5 * seed)
            view = View(o)
            if len(view.hidden) != 2:
                continue
            classes = Classes(view)
            feats = Features(view)
            picks = np.random.default_rng(seed).integers(0, len(classes), 20)
            worlds = classes.worlds(picks, np.random.default_rng(seed))
            np.testing.assert_array_equal(feats.of(worlds), feats.of_classes(classes)[picks])
            self.assertEqual(len(feats), feats.of(worlds).shape[1])


class PlanPlayerTests(Fixture):
    def plan(self, **stage):
        p = self.make(PlanPlayer, list_from_trick=14)
        p.playouts = playout_stages(dict(dict(from_trick=1, to_trick=13, root_margin=13.), **stage))
        return p

    def test_settings_are_checked(self):
        with self.assertRaises(ValueError):
            PlayoutUse(seat='nobody')
        with self.assertRaises(ValueError):
            PlayoutUse(trust=-1.)
        with self.assertRaises(ValueError):
            playout_stages([dict(from_trick=3, to_trick=6), dict(from_trick=6, to_trick=8)])
        with self.assertRaises(ValueError):
            playout_stages(dict(depth=2))
        self.assertEqual(playout_stages(None), ())

    def test_without_trust_it_is_gen7_card_for_card(self):
        """Trust 0 leaves the search's best cards eligible, so the same card is played from the same random stream."""
        plain, plan = self.make(list_from_trick=14), self.plan(trust=0., seat='top')
        consulted = 0
        for seed in range(6):
            game, o, world = spot(seed, 9 + 4 * seed)
            if len(o.legal) < 2:
                continue
            a = plain.choose(o, random.Random(seed))
            b = plan.choose(o, random.Random(seed))
            self.assertEqual(a.card, b.card)
            consulted += bool(b.details.get('gen7_tree', {}).get('consulted'))
        self.assertGreater(consulted, 0)

    def test_the_note_holds_the_search_and_the_playouts(self):
        for seat in ('top', 'map'):
            plan = self.plan(trust=1., seat=seat)
            found = False
            for seed in range(8):
                game, o, world = spot(seed, 10 + 4 * seed)
                if len(o.legal) < 2:
                    continue
                d = plan.choose(o, random.Random(seed))
                note = d.details.get('gen7_tree')
                if not note or not note['consulted']:
                    continue
                found = True
                self.assertIn(d.card, o.legal)
                self.assertEqual(note['kind'], 'playout')
                kept = [c for c in note['candidates'] if c['kept']]
                self.assertTrue(kept)
                top = max(c['adjusted'] for c in note['candidates'])
                self.assertTrue(all(abs(c['adjusted'] - top) < 1e-9 for c in kept))
                for c in note['candidates']:        # adjusted = estimate + trust x (playout - double dummy on the same layouts)
                    estimate = d.details['estimates'][c['searched']]['utility']
                    self.assertAlmostEqual(c['adjusted'], estimate + (c['tree'] - c['same_layouts']), places=9)
            self.assertTrue(found)


if __name__ == '__main__':
    unittest.main()
