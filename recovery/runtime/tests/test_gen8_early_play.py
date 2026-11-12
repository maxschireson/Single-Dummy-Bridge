"""Gen 8 prototype: reading the play before the deal list (Gen7Config.early_play_weight)."""
import unittest

import numpy as np

from bridge_harness.corpus import generate
from bridge_harness.gen6 import View
from bridge_harness.gen7 import Gen7Config, hidden_plays, resolved
from bridge_harness.players import GreedyPlayer
from bridge_harness.runner import play_table, replay
from test_gen7 import Fixture, played


def early_positions(seeds, plies):
    """Positions after the opening lead and before trick 6, two hidden hands, a choice to make."""
    for seed in seeds:
        for n in plies:
            board, game, before = played(seed, n)
            o = game.observation()
            if len(View(o).hidden) == 2 and len(o.legal) > 1:
                yield o, game


class EarlyPlayTests(Fixture):
    def test_off_by_default_and_validated(self):
        self.assertEqual(Gen7Config().early_play_weight, 0.)
        self.assertNotIn('early_pool', resolved(None))                      # a Gen 7 bot's settings read as before
        self.assertEqual(resolved(dict(early_play_weight=.5))['early_pool'], 512)
        for bad in (dict(early_play_weight=-1), dict(early_pool=4), dict(early_min_effective=0)):
            with self.assertRaises(ValueError):
                Gen7Config(**bad)

    def test_early_layouts_fit_the_cards_and_the_play_weights_them(self):
        p = self.make(gen7=dict(early_play_weight=1., early_pool=128, early_min_effective=1.), list_from_trick=14, mid_from_trick=1)
        checked = 0
        for o, game in early_positions(range(12), (5, 9, 14, 18)):
            view = View(o)
            source = p.source(o, view)
            self.assertNotEqual(source, 'list')
            fit = {}
            p.play_log_likelihood = lambda o_, v_, assign, plays: fit.setdefault('ll', -2. * (assign[:, 0] == 0))     # layouts giving the first unseen card to hidden hand 0 are e^2 less likely
            worlds, weights, info = p.weighted_layouts(o, view, source, np.random.default_rng(checked))
            del p.play_log_likelihood
            self.assertAlmostEqual(float(np.sum(weights)), 1.)
            self.assertEqual(info['pick'], 'play-pool')
            self.assertEqual(info['play_decisions'], len(hidden_plays(o)))
            first = int(view.unseen[0])
            for w in worlds:
                self.assertEqual(sorted(c for s in view.hidden for c in w[s]), view.unseen.tolist())
                self.assertEqual([len(w[s]) for s in view.hidden], view.caps)
                for s in range(4):
                    if o.known_hands[s] is not None:
                        self.assertEqual(w[s], o.known_hands[s])
            pool_share = float(np.mean(fit['ll'] < 0))                  # share of the pool with the card in hand 0
            if 0.2 < pool_share < 0.8:
                solved_share = sum(wt for w, wt in zip(worlds, weights) if first in w[view.hidden[0]])
                expected = pool_share * np.exp(-2.) / (pool_share * np.exp(-2.) + 1 - pool_share)
                self.assertLess(abs(solved_share - expected), 0.12)
                checked += 1
        self.assertGreater(checked, 8)

    def test_the_exponent_backs_off_when_the_play_fits_too_few_layouts(self):
        p = self.make(gen7=dict(early_play_weight=1., early_pool=128, early_min_effective=24.), list_from_trick=14)
        o, game = next(early_positions(range(40, 60), (9,)))
        view = View(o)
        sharp = lambda o_, v_, assign, plays: -30. * np.arange(len(assign), dtype=float)        # one layout towers over the rest
        p.play_log_likelihood = sharp
        worlds, weights, info = p.weighted_layouts(o, view, p.source(o, view), np.random.default_rng(1))
        self.assertLess(info['play_power'], 1.)
        self.assertGreaterEqual(info['effective_with_play'], 24.)
        self.assertGreater(len(worlds), 8)

    def test_no_hidden_play_or_weight_zero_is_gen7(self):
        on = self.make(gen7=dict(early_play_weight=.5), list_from_trick=14)
        off = self.make(gen7=dict(early_play_weight=0.), list_from_trick=14)
        o, game = next(early_positions(range(70, 90), (9,)))
        view = View(o)
        a = off.weighted_layouts(o, view, off.source(o, view), np.random.default_rng(3))
        b = super(type(off), off).layouts(o, view, off.source(o, view), np.random.default_rng(3))
        self.assertEqual(a[0], b[0])
        self.assertNotIn('pool', a[2])
        self.assertEqual(on.weighted_layouts(o, view, on.source(o, view), np.random.default_rng(3))[2]['pick'], 'play-pool')

    def test_whole_tables_play_and_replay_with_early_play_weights(self):
        six = self.make(gen7=dict(early_play_weight=.5, early_pool=64))
        seen = 0
        for seed in (2, 3):
            board = next(generate(1, 900 + seed))
            for room in (0, 1):
                result = play_table(board, ['7' if s % 2 == room else 'g' for s in range(4)], {'7': six, 'g': GreedyPlayer()}, seed=5)
                self.assertEqual(result['status'], 'ok', result.get('traceback'))
                replay(dict(board=board.to_dict(), tables=[result]))
                for a in result['actions']:
                    g = a.get('gen6') or {}
                    if g.get('pick') == 'play-pool':
                        seen += 1
                        self.assertGreater(g['play_net_rows'], 0)
                        self.assertLessEqual(g['play_power'], .5)
        self.assertGreater(seen, 10)


if __name__ == '__main__':
    unittest.main()


class CardingRuleTests(Fixture):
    def test_fixed_carding_rules_choose_among_the_tied_cards_only(self):
        from bridge_harness.core import card
        boards = [next(generate(1, 950 + s)) for s in range(2)]
        for rule in ('low', 'high', 'random'):
            p = self.make(gen7=dict(tie_break=rule, play_weight=0.))
            chosen = 0
            for board in boards:
                result = play_table(board, ['7', 'g', '7', 'g'], {'7': p, 'g': GreedyPlayer()}, seed=5)
                self.assertEqual(result['status'], 'ok', result.get('traceback'))
                for a in result['actions']:
                    if str(a.get('selector', '')).startswith('rule-' + rule):
                        tied = sorted(card(k) for k, q in a['proposal_probabilities'].items() if q > 0)
                        self.assertGreater(len(tied), 1)
                        self.assertIn(card(a['card']), tied)
                        self.assertLessEqual(a['selected_pimc_gap'], 1e-9)
                        if rule == 'low':
                            self.assertEqual(card(a['card']) % 13, min(x % 13 for x in tied))
                        if rule == 'high':
                            self.assertEqual(card(a['card']) % 13, max(x % 13 for x in tied))
                        chosen += 1
            self.assertGreater(chosen, 10)


class OpponentTypeTests(Fixture):
    def test_opponent_factor_scales_only_the_opponents_plays(self):
        def player(weights, opponent):
            spec_extra = dict(early_play_weight=1., opponent_play_weight=weights)
            p = self.make(gen7=spec_extra, list_from_trick=14)
            p.opponent_factor = float(weights.get(opponent, weights.get('*', 1.)))
            return p
        full, half, none = player({}, 'x'), player({'x': .5}, 'x'), player({'*': 0.}, 'y')
        self.assertEqual((full.opponent_factor, half.opponent_factor, none.opponent_factor), (1., .5, 0.))
        seen = 0
        for o, game in early_positions(range(20, 60), (9, 13)):
            view = View(o)
            plays = hidden_plays(o)
            partner = [ch % 2 == o.controller % 2 for _, _, ch in plays]
            if not any(partner) or all(partner):
                continue
            assign = view.uniform(24, np.random.default_rng(0))
            a, b, c = (p.play_log_likelihood(o, view, assign, plays) for p in (full, half, none))
            own = full.play_log_likelihood(o, view, assign, [x for x, mine in zip(plays, partner) if mine])
            self.assertTrue(np.allclose(c, own))                            # factor 0: only partner's plays are read
            self.assertTrue(np.allclose(b, own + .5 * (a - own)))
            seen += 1
            if seen >= 4:
                break
        self.assertGreaterEqual(seen, 2)
        told = self.make(gen7=dict(early_play_weight=1., opponent_play_weight={'x': .5, '*': .25}), list_from_trick=14)
        self.assertEqual(told.opponent_factor, .25)                         # nobody named yet: any other opponent
        told.meet('x')                                                      # what run_board does for every board
        self.assertEqual(told.opponent_factor, .5)
        told.meet('someone-else')
        self.assertEqual(told.opponent_factor, .25)
        with self.assertRaises(ValueError):
            Gen7Config(opponent_play_weight={'x': -1})
        self.assertNotIn('opponent_play_weight', resolved(None))
        self.assertEqual(resolved(dict(opponent_play_weight={'x': 0}))['opponent_play_weight'], {'x': 0})
