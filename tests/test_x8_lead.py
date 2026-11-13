"""The opening lead from rollouts (x8_player's `lead` block): layouts of three hidden hands, their codes in the record,
the rows' view of each layout's own dummy, and the decision."""
import json
import random
import unittest

import numpy as np

from bridge_harness import x8_capture
from bridge_harness.core import Board, Contract, Game, symbol
from bridge_harness.corpus import generate
from bridge_harness.gen6 import View
from bridge_harness.gen7_net import INPUTS
from bridge_harness.plan_rollout import Public, Rows, inputs
from bridge_harness.x8_player import game_or_doubled, resolved, touching, x8_settings
from test_x8 import Fixture8, spot


def dealt(o, rng):
    """A layout the opening leader cannot rule out: the three hands it cannot see dealt at random."""
    view = View(o)
    return view.world(view.uniform(1, np.random.default_rng(rng.getrandbits(32)))[0])


class LeadCodeTests(unittest.TestCase):
    def test_three_hidden_hands_round_trip(self):
        for seed in range(6):
            _, o, _ = spot(seed, 0)
            self.assertEqual(sum(h is None for h in o.known_hands), 3)
            rng = random.Random(seed)
            worlds = [dealt(o, rng) for _ in range(5)]
            self.assertEqual(len(set(worlds)), 5)
            for w in worlds:
                code = x8_capture.layout_code(o, w)
                self.assertLess(int(code, 16), 3 ** 39)
                self.assertEqual(x8_capture.layout_world(o, code), w)
            tricks = np.arange(10, dtype=np.int16).reshape(5, 2)
            weights = np.array([.1, .4, .2, .05, .25])
            cap = x8_capture.capture_block(o, worlds, weights, tricks, tricks % 2 == 0, 3)
            json.dumps(cap)
            got_worlds, got_w, got_t, _ = x8_capture.read_capture(o, cap)
            self.assertEqual(got_worlds, [worlds[i] for i in (1, 4, 2)])
            np.testing.assert_array_equal(got_t, tricks[[1, 4, 2]])

    def test_two_hidden_hands_are_coded_as_before(self):
        _, o, world = spot(3, 9)
        hidden, unseen = x8_capture.hidden_of(o)
        self.assertEqual(len(hidden), 2)
        second = set(world[hidden[1]])
        self.assertEqual(x8_capture.layout_code(o, world), '%x' % sum(1 << k for k, c in enumerate(unseen) if c in second))


class LeadSettingsTests(unittest.TestCase):
    def test_the_block_is_a_rollout_stage_with_its_own_defaults(self):
        self.assertIsNone(x8_settings(None).lead)
        self.assertNotIn('lead', resolved(None))            # a bot without the block pins what it always pinned
        self.assertNotIn('lead', resolved(dict(stages=[dict(from_trick=1, to_trick=13, mode='rollout')])))
        c = x8_settings(dict(lead={}))
        self.assertEqual((c.lead.mode, c.lead.layouts, c.lead.cards, c.lead.prior, c.lead.race), ('rollout', 512, 13, 0., 0.))
        self.assertEqual(c.lead_capture, 0)
        r = resolved(dict(lead=dict(layouts=64, seat='draw', capture=32)))
        self.assertEqual((r['lead']['layouts'], r['lead']['seat'], r['lead']['capture'], r['lead']['cards']), (64, 'draw', 32, 13))
        json.dumps(r)

    def test_bad_lead_settings_are_refused(self):
        for bad in (dict(mode='blend'), dict(from_trick=2, to_trick=2), dict(to_trick=3), dict(capture=-1), dict(capture=True),
                    dict(layouts=0), dict(depth=3), dict(capture=5000)):
            with self.assertRaises(ValueError, msg=str(bad)):
                x8_settings(dict(lead=bad))


class LeadRowsTests(Fixture8):
    def test_every_row_sees_its_own_layouts_dummy(self):
        """After the lead, each row's inputs equal the encoder on the Observation the game gives in that row's layout,
        to the last card: the rows differ in dummy, not only in the two hands that stay hidden."""
        p = self.make8()
        for seed in range(4):
            _, o, _ = spot(seed, 0)
            rng = random.Random(seed)
            worlds = [dealt(o, rng) for _ in range(3)]
            self.assertEqual(len({w[o.contract.dummy] for w in worlds}), 3)
            lead = rng.choice(o.legal)
            games = [Game(x8_capture.imagined_board(o, w)) for w in worlds]
            rows, public = Rows(o, worlds), Public(p.net, o)
            rows.play([lead] * 3)
            for g in games:
                g.play(lead)
            while not games[0].done:
                got = inputs(rows, public)
                cards = []
                for i, g in enumerate(games):
                    now = g.observation()
                    want = p.net.encode(now)
                    for k in INPUTS:
                        np.testing.assert_array_equal(np.asarray(want[k], np.float32), np.asarray(got[k][i], np.float32), err_msg=f'{k} seed {seed} row {i}')
                    cards.append(rng.choice(now.legal))
                    g.play(cards[-1])
                rows.play(cards)
            self.assertEqual([int(x) for x in rows.won], [g.declarer_tricks for g in games])


class LeadPlayerTests(Fixture8):
    GEN8 = dict(play_weight=1., early_play_weight=1., early_pool=32, early_min_effective=4.)

    def leads(self, p, seeds):
        """(action, Observation, board) for the opening lead of every table the 8X bot leads at."""
        for seed in seeds:
            board = next(generate(1, 700 + seed))
            for room in (0, 1):
                a, o = next(iter(self.views(board, self.table(p, board, room))))
                self.assertEqual(a['ply'], 0)
                if a['player'] == 'x':
                    yield a, o, board

    def check(self, a, o, layouts, kept):
        note = a['x8']
        self.assertEqual((note['mode'], note['lead'], note['trick']), ('rollout', True, 1))
        self.assertNotIn('estimates', a)                    # nothing was solved
        self.assertEqual(a['dds_calls'], 0)
        runs = touching(o)
        self.assertEqual(len(note['cards']), len(runs))     # every distinct lead is a candidate
        self.assertEqual(sorted(x for run in note['runs'] for x in run), sorted(symbol(x) for x in o.legal))
        self.assertLessEqual(note['layouts'], layouts)
        self.assertEqual(set(note['n']), {note['layouts']})  # each on every layout
        self.assertEqual(len(note['rounds']), 1)
        self.assertEqual(note['alive'], list(range(len(runs))))
        best = max(note['value'])
        self.assertAlmostEqual(note['value'][[j for j, run in enumerate(note['runs']) if a['card'] in run][0]], best, places=6)
        self.assertAlmostEqual(sum(a['behavior_probabilities'].values()), 1., places=9)
        worlds, w, tricks, floor = x8_capture.read_capture(o, note['cap'])
        self.assertEqual(len(worlds), min(kept, note['layouts']))
        self.assertEqual(tricks.shape, (len(worlds), len(runs)))
        self.assertTrue(((tricks >= 0) & (tricks <= 13)).all())
        for world in worlds:                                # the leader's own hand as it is; the other three dealt, 13 each
            self.assertEqual(world[o.controller], o.known_hands[o.controller])
            self.assertEqual([len(h) for h in world], [13] * 4)
            self.assertEqual(sorted(c for h in world for c in h), list(range(52)))
        self.assertGreater(len({world[o.contract.dummy] for world in worlds}), 1)
        for row in note['forks']:
            view = x8_capture.fork_view(o, row)[0]
            self.assertEqual(len(view.history), 1 + len(row[2]))
            self.assertIsNotNone(view.known_hands[o.contract.dummy])
        return note

    def test_the_lead_is_rolled_out_on_three_hand_layouts_from_the_lead_net(self):
        x8 = dict(lead=dict(layouts=12, seat='top', capture=10), capture=dict(level=2, forks=4, layouts=4))
        p = self.make8(x8, gen7=self.GEN8, list_solve=16)
        seen = forks = 0
        for a, o, _ in self.leads(p, (2, 3, 4)):
            note = self.check(a, o, 12, 10)
            self.assertEqual(a['gen6']['source'], 'lead_net')
            forks += len(note['forks'])
            seen += 1
        self.assertGreaterEqual(seen, 3)
        self.assertGreater(forks, 3)

    def test_where_the_scorer_has_to_lead_its_weighted_pool_is_drawn(self):
        x8 = dict(lead=dict(layouts=10, seat='draw'), capture=dict(level=2, forks=0, layouts=6))
        p = self.make8(x8, gen7=self.GEN8, list_solve=16, lead_source='scorer', lead_pool=64)
        seen = 0
        for a, o, _ in self.leads(p, (2, 3)):
            self.check(a, o, 10, 6)                         # no lead capture count: the capture block's `layouts`
            self.assertEqual((a['gen6']['source'], a['gen6']['pool']), ('scorer', 160))
            seen += 1
        self.assertGreaterEqual(seen, 2)

    def test_without_the_block_the_lead_is_not_rolled_out_and_a_games_only_block_leaves_partscores(self):
        plain = self.make8(dict(stages=[dict(from_trick=1, to_trick=13, mode='rollout', layouts=8, first=4)]), gen7=self.GEN8, list_solve=16)
        for a, _, _ in self.leads(plain, (2, 3)):
            self.assertNotEqual((a.get('x8') or {}).get('mode'), 'rollout')
        games = self.make8(dict(lead=dict(layouts=8, contracts='games')), gen7=self.GEN8, list_solve=16)
        games.meet('g')
        hands = next(generate(1, 702)).hands
        for contract, game in ((Contract(2, 'S', 0), False), (Contract(3, 'N', 0), True), (Contract(4, 'D', 2), False),
                               (Contract(1, 'N', 0, 1), True), (Contract(6, 'S', 2), True)):
            o = Game(Board('t', hands, contract, 0, 'None', ())).observation()
            self.assertEqual(game_or_doubled(contract), game)
            details = games.choose(o, random.Random(1)).details
            self.assertEqual((details.get('x8') or {}).get('mode') == 'rollout', game, str(contract))

    def test_the_same_seed_leads_the_same_card(self):
        x8 = dict(lead=dict(layouts=8, seat='draw'))
        first = [(a['card'], a['x8']['value']) for a, _, _ in self.leads(self.make8(x8, gen7=self.GEN8, list_solve=16), (2, 3))]
        again = [(a['card'], a['x8']['value']) for a, _, _ in self.leads(self.make8(x8, gen7=self.GEN8, list_solve=16), (2, 3))]
        self.assertEqual(first, again)


if __name__ == '__main__':
    unittest.main()
