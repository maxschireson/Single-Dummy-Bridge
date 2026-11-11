"""Gen7 alpha: the tree search inside the player, driven by spec['gen7']['tree'] (bridge_harness/gen7.py)."""
from dataclasses import asdict, fields
import json
import random
import unittest
from unittest.mock import patch

import numpy as np

from bridge_harness.core import card, symbol
from bridge_harness.corpus import generate
from bridge_harness.gen6 import Gen6Player
from bridge_harness.gen7 import USE_KEYS, Gen7Config, TreeUse, gen7_settings, resolved, tree_stages, utilities
from bridge_harness.gen7_tree import OverBudget, Tree, TreeConfig
from bridge_harness.players import GreedyPlayer
from bridge_harness.runner import play_table, replay
from test_gen7 import Fixture, played

OFF = dict(play_weight=0., tie_break='gen5')        # the switches that leave Gen6's play alone
WIDE = dict(from_trick=1, root_margin=13., root_cards=13)       # every distinguishable card is a candidate


class SettingsTests(unittest.TestCase):
    def test_one_stage_splits_into_use_and_search_settings(self):
        config, stages = gen7_settings(dict(play_weight=.25, tree=dict(from_trick=4, to_trick=9, root_margin=.25, root_cards=2, trust=.5,
                                                                       max_solves=500, tricks=3, breadth=3, mass=.95, layouts=16, reply='dd')))
        self.assertEqual(config, Gen7Config(play_weight=.25))
        self.assertEqual(stages, (TreeUse(4, 9, .25, 2, .5, 500, TreeConfig(tricks=3, breadth=3, mass=.95, layouts=16, reply='dd')),))

    def test_no_tree_means_no_stages(self):
        for block in (None, {}, dict(tie_break='gen5'), dict(tree=None), dict(tree=[])):
            self.assertEqual(gen7_settings(block)[1], ())
        self.assertNotIn('tree', resolved(dict(tie_break='gen5')))

    def test_stages_in_a_list_must_not_share_a_trick(self):
        stages = tree_stages([dict(from_trick=3, to_trick=6, tricks=2), dict(from_trick=7, tricks=3, layouts=16)])
        self.assertEqual([(s.from_trick, s.to_trick, s.search.tricks, s.search.layouts) for s in stages], [(3, 6, 2, 8), (7, 13, 3, 16)])
        with self.assertRaises(ValueError):
            tree_stages([dict(from_trick=3, to_trick=7), dict(from_trick=7)])

    def test_bad_settings_are_refused(self):
        for bad in (dict(depth=2), dict(root_cards=1), dict(from_trick=5, to_trick=4), dict(from_trick=0), dict(trust=-1.), dict(tricks=14),
                    dict(reply='oracle'), dict(own='guess'), dict(layouts=0), dict(max_solves=-1), dict(root_cards=2.5), dict(tricks=True),
                    dict(reply_layouts=9, reply_pool=8), 'two tricks', [3]):
            with self.assertRaises(ValueError, msg=repr(bad)):
                tree_stages(bad)
        with self.assertRaises(ValueError):
            gen7_settings(dict(tie_break='coin'))

    def test_resolved_writes_out_every_setting_and_reads_back_the_same(self):
        block = dict(tie_break='gen5', tree=[dict(to_trick=6), dict(from_trick=7, tricks=3, reply='search')])
        full = resolved(block)
        self.assertEqual(set(full), {f.name for f in fields(Gen7Config)} | {'tree'})
        for stage in full['tree']:
            self.assertEqual(set(stage), set(USE_KEYS) | {f.name for f in fields(TreeConfig)})
        self.assertEqual(gen7_settings(full), gen7_settings(block))
        self.assertEqual(resolved(full), full)
        json.dumps(full, allow_nan=False)


class TreeInThePlayerTests(Fixture):
    def table(self, p, board, room, seed=5):
        result = play_table(board, ['x' if s % 2 == room else 'g' for s in range(4)], {'x': p, 'g': GreedyPlayer()}, seed=seed)
        self.assertEqual(result['status'], 'ok', result.get('traceback'))
        replay(dict(board=board.to_dict(), tables=[result]))
        json.dumps(result, allow_nan=False)
        return result

    def tables(self, p, seeds=(2, 3)):
        return [self.table(p, next(generate(1, 700 + seed)), room) for seed in seeds for room in (0, 1)]

    def mine(self, tables):
        return [a for t in tables for a in t['actions'] if a['player'] == 'x' and 'gen6' in a]

    # ---- nothing changes unless the tree says so -----------------------------------------
    def test_no_trust_or_no_horizon_plays_gen6s_game_card_for_card(self):
        six = self.tables(self.make(Gen6Player, list_solve=16))
        for tree in (dict(WIDE, trust=0., tricks=1, layouts=4), dict(WIDE, tricks=0, layouts=4)):
            seven = self.tables(self.make(gen7=dict(OFF, tree=tree), list_solve=16))
            consulted = 0
            for a, b in zip(six, seven):
                self.assertEqual([x['card'] for x in a['actions']], [x['card'] for x in b['actions']])
                for x, y in zip(a['actions'], b['actions']):
                    if x['player'] == 'x' and 'gen6' in x:
                        self.assertEqual(x['estimates'], y['estimates'])
                        self.assertEqual(x['behavior_probabilities'], y['behavior_probabilities'])
                        consulted += bool(y.get('gen7_tree', {}).get('consulted'))
            self.assertGreater(consulted, 10)

    def test_the_opening_lead_and_tricks_outside_every_stage_are_gen6s(self):
        p = self.make(gen7=dict(OFF, tree=[dict(from_trick=4, to_trick=5, root_margin=13., root_cards=13, tricks=1, layouts=2),
                                           dict(from_trick=8, to_trick=9, root_margin=13., root_cards=13, tricks=0, layouts=2)]), list_solve=16)
        seen = set()
        for a in self.mine(self.tables(p)):
            trick = a['ply'] // 4 + 1
            stage = 0 if 4 <= trick <= 5 else 1 if 8 <= trick <= 9 else None
            if a['ply'] == 0 or stage is None:
                self.assertNotIn('gen7_tree', a)
            else:
                self.assertEqual(a['gen7_tree']['stage'], stage)
                seen.add(stage)
        self.assertEqual(seen, {0, 1})

    # ---- what the tree's answer does -----------------------------------------------------
    def test_value_is_the_estimate_plus_trust_times_what_the_tree_changed(self):
        """A tree that adds a trick to its last candidate: that candidate is played, and the record adds up."""
        def values(tree, o, worlds, weights, cards=None):
            self.assertAlmostEqual(float(np.sum(weights)), 1.)
            self.assertLessEqual(len(worlds), 4)
            plain = {x: sum(w * utilities(o, v)[x] for (v, _), w in zip(tree.dds.solve_batch(
                worlds, o.contract.trump, o.leader, o.trick, fixed_seats=[s for s, h in enumerate(o.known_hands) if h is not None]), weights))
                for x in cards}
            return {x: plain[x] + (x == cards[-1]) for x in cards}
        p = self.make(gen7=dict(OFF, tree=dict(from_trick=1, root_margin=.5, root_cards=3, trust=.75, tricks=1, layouts=4)), list_solve=16)
        with patch.object(Tree, 'values', values):
            actions = self.mine(self.tables(p))
        consulted = [a for a in actions if a.get('gen7_tree', {}).get('consulted')]
        self.assertGreater(len(consulted), 10)
        switched = 0
        for a in consulted:
            t = a['gen7_tree']
            cands = t['candidates']
            self.assertTrue(2 <= len(cands) <= 3)
            best = max(v['utility'] for v in a['estimates'].values())
            listed = [c for x in cands for c in x['cards']]
            self.assertEqual(len(listed), len(set(listed)))
            for x in cands:
                self.assertIn(x['searched'], x['cards'])
                self.assertLessEqual(x['gap'], .5 + 1e-9)
                for c in x['cards']:
                    self.assertAlmostEqual(a['estimates'][c]['utility'], best - x['gap'])
                self.assertAlmostEqual(x['adjusted'], best - x['gap'] + .75 * (x['tree'] - x['same_layouts']))
            self.assertEqual([x['gap'] for x in cands], sorted(x['gap'] for x in cands))
            self.assertAlmostEqual(cands[-1]['tree'] - cands[-1]['same_layouts'], 1.)
            for x in cands[:-1]:
                self.assertAlmostEqual(x['tree'], x['same_layouts'])
            # 0.75 of a trick outweighs any gap inside the half-trick margin: the last candidate alone is kept
            self.assertEqual([x['kept'] for x in cands], [False] * (len(cands) - 1) + [True])
            self.assertIn(a['card'], cands[-1]['cards'])
            proposal = a.get('proposal_probabilities', a['behavior_probabilities'])
            self.assertEqual({c for c, q in proposal.items() if q > 0}, set(cands[-1]['cards']))
            self.assertAlmostEqual(sum(proposal.values()), 1.)
            self.assertAlmostEqual(a['selected_pimc_gap'], cands[-1]['gap'])
            self.assertTrue(set(t['gen6_cards']) <= set(a['estimates']))
            switched += a['selected_pimc_gap'] > 1e-9
        self.assertGreater(switched, 3)

    def test_cards_the_solves_cannot_tell_apart_are_one_candidate(self):
        """Two layouts; S-cards level in both, a third card level on average only. Two candidates, not three."""
        for seed in range(40):
            board, game, before = played(seed, 9 + seed % 3)
            o = game.observation()
            suits = {}
            for x in o.legal:
                suits.setdefault(x // 13, []).append(x)
            if len(o.legal) >= 3 and any(len(v) >= 2 for v in suits.values()) and len(suits) >= 2:
                break
        twins = next(v for v in suits.values() if len(v) >= 2)[:2]
        other = next(v for k, v in suits.items() if twins[0] not in v)[0]
        rest = [x for x in o.legal if x not in (*twins, other)]
        solved = [({**{x: 5 for x in twins}, other: 6, **{x: 0 for x in rest}}, 1), ({**{x: 5 for x in twins}, other: 4, **{x: 0 for x in rest}}, 1)]
        p = self.make(gen7=dict(OFF, tree=dict(from_trick=1, root_margin=0., root_cards=13, tricks=1, layouts=2)))
        p.solved_layouts = [None, None]
        calls = []
        def values(tree, o, worlds, weights, cards=None):
            calls.append(list(cards))
            return {x: 0. for x in cards}
        stats = dict(native_solves=0, hits=0, duplicate_worlds=0)
        with patch.object(Tree, 'values', values):
            got = p.search_decision(o, random.Random(1), solved, [.5, .5], stats, stats, {})
        t = got.details['gen7_tree']
        self.assertTrue(t['consulted'])
        self.assertEqual(sorted(sorted(x['cards']) for x in t['candidates']), sorted([sorted(symbol(x) for x in twins), [symbol(other)]]))
        self.assertEqual(len(calls[0]), 2)
        self.assertEqual({q for q in got.details['behavior_probabilities'].values()}, {0., 1 / 3} if rest else {1 / 3})

    def test_only_decisions_with_two_candidates_are_searched(self):
        calls = []
        def values(tree, o, worlds, weights, cards=None):
            calls.append(len(cards))
            return {x: 0. for x in cards}
        p = self.make(gen7=dict(OFF, tree=dict(from_trick=1, root_margin=0., root_cards=2, tricks=1, layouts=4)), list_solve=16)
        with patch.object(Tree, 'values', values):
            actions = self.mine(self.tables(p, seeds=(2,)))
        notes = [a['gen7_tree'] for a in actions if 'gen7_tree' in a]
        alone = [t for t in notes if t['candidates'] == 1]
        self.assertGreater(len(alone), 3)
        self.assertFalse(any(t['consulted'] for t in alone))
        self.assertEqual(len(calls), sum(t['consulted'] for t in notes))
        self.assertEqual(set(calls), {2})

    def test_over_budget_keeps_gen6s_card(self):
        six = self.tables(self.make(Gen6Player, list_solve=16), seeds=(2,))
        seven = self.tables(self.make(gen7=dict(OFF, tree=dict(WIDE, max_solves=1, tricks=1, layouts=4)), list_solve=16), seeds=(2,))
        for a, b in zip(six, seven):
            self.assertEqual([x['card'] for x in a['actions']], [x['card'] for x in b['actions']])
        notes = [a['gen7_tree'] for a in self.mine(seven) if 'gen7_tree' in a and a['gen7_tree'].get('candidates', 0) != 1]
        self.assertGreater(len(notes), 10)
        self.assertTrue(all(t.get('over_budget') and not t['consulted'] for t in notes))
        with self.assertRaises(OverBudget):
            Tree(None, None, TreeConfig(), max_solves=3).spend(4)

    # ---- real trees, whole tables --------------------------------------------------------
    def test_whole_tables_with_the_tree_deciding(self):
        for tree in (dict(from_trick=1, root_margin=.5, root_cards=3, tricks=2, breadth=2, layouts=4),
                     dict(from_trick=2, root_margin=.25, root_cards=2, tricks=1, breadth=2, layouts=3, reply='search', own='search',
                          reply_layouts=2, reply_pool=4),
                     dict(from_trick=2, root_margin=.25, root_cards=2, tricks=2, breadth=1, layouts=3, reply='dd', own='net')):
            p = self.make(gen7=dict(tree=tree), list_solve=16, list_from_trick=5)
            actions = self.mine(self.tables(p, seeds=(2,)))
            consulted = [a['gen7_tree'] for a in actions if a.get('gen7_tree', {}).get('consulted')]
            self.assertGreater(len(consulted), 3, tree)
            for a in actions:
                self.assertLessEqual(a['selected_pimc_gap'], tree['root_margin'] + 1e-9)
                self.assertEqual(a['gen7'], asdict(p.g7))
            self.assertGreater(sum(t['solves'] for t in consulted), 0)
            for t in consulted:
                self.assertGreater(t['nodes'], 0)       # no solves when every line reaches the end of the hand
                self.assertLessEqual(t['layouts'], tree['layouts'])
                self.assertTrue(any(x['kept'] for x in t['candidates']))
            if tree.get('reply') == 'search':
                self.assertGreater(sum(t['replies'] for t in consulted), 0)
            self.assertEqual(asdict(p.stages[0].search)['tricks'], tree['tricks'])

    def test_a_tree_that_needs_a_replier_gets_one_from_the_player(self):
        p = self.make(gen7=dict(tree=dict(reply='search', reply_layouts=2, reply_pool=4)))
        self.assertIsNotNone(p.replier(p.stages[0].search))
        self.assertIsNone(p.replier(TreeConfig()))
        with self.assertRaises(ValueError):
            Tree(p.net, p.dds, TreeConfig(own='search'))


if __name__ == '__main__':
    unittest.main()
