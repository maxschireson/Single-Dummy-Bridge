"""The 8X bot: batched rollouts (x8_rollout.py), the winning-line logic (x8_claims.py), the record (x8_capture.py)
and the player (x8_player.py)."""
import json
import os
from pathlib import Path
import random
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from bridge_harness import claims, x8_capture, x8_claims
from bridge_harness.core import Board, Contract, Game, card, symbol
from bridge_harness.corpus import generate
from bridge_harness.gen6 import View
from bridge_harness.gen7 import Gen7Player
from bridge_harness.plan_rollout import NetPlayer, Public, Rows, card_values
from bridge_harness.players import GreedyPlayer
from bridge_harness.runner import decision_rng, play_table, replay
from bridge_harness.x8_player import Stage, X8Player, paired, player, resolved, touching, worth, x8_settings
from bridge_harness.x8_rollout import Seats, evaluate, runs_with
from test_gen6 import FakeBelief, FakeState
from test_gen7 import Fixture, played

BIN = os.environ.get('SURE_BIN', '')
HAVE_SOLVER = bool(BIN) and os.path.exists(BIN)


def spot(seed, plies):
    """A random game after `plies` cards: (game, Observation, the four hands as they stand)."""
    board, game, _ = played(seed, plies)
    return game, game.observation(), tuple(tuple(sorted(h)) for h in game.hands)


def shuffled(o, world, rng):
    """Another layout the decider cannot rule out: the two hands it cannot see dealt again at random, hand sizes and
    show-outs kept (`world` is the true one and only fixes the call's shape)."""
    view = View(o)
    return view.world(view.uniform(1, np.random.default_rng(rng.getrandbits(32)))[0])


class Fixture8(Fixture):
    def make8(self, x8=None, gen7=None, cls=X8Player, **switches):
        spec = dict(id='8x-test', engine='gen8x', samples=8, near_tie=0., exploration=0., scorer='scorer.npz', lead_belief='lead.npz',
                    lead_state_bidder='bidder.keras', belief='belief.npz', belief_kind='public', gen6=switches,
                    gen7_policy='gen7.npz', gen7=gen7 or {}, x8=x8 or {})
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

    def views(self, board, result):
        """(action, the Observation it was chosen from) for every action of a played table."""
        game = Game(board)
        for a in result['actions']:
            yield a, game.observation()
            game.play(card(a['card']))


class SettingsTests(unittest.TestCase):
    def test_defaults_are_inert_and_written_out(self):
        r = resolved(None)
        self.assertEqual(r['stages'], [])
        self.assertEqual(r['claims']['cards'], 0)
        self.assertEqual(r['mix'], dict(declarer=False, defender=False, near=0., read_declarer=[], read_defender=[],
                                        declarer_power=0., defender_power=0.))
        full = resolved(dict(stages=[dict(from_trick=3, to_trick=6, mode='blend', trust=.25)], claims=dict(cards=10, opponents=['a'])))
        self.assertEqual(full['stages'][0]['layouts'], 128)
        self.assertEqual(full['claims']['opponents'], ['a'])
        json.dumps(full)

    def test_later_settings_are_pinned_only_where_set(self):
        """The seat settings of 14 November (cut, seat_other, power_other, cut_other) and `blind` are written into a
        manifest only where a bot sets them, so a bot without them pins what it always pinned."""
        old = resolved(dict(stages=[dict(mode='rollout', from_trick=1, seat='draw')], lead=dict(layouts=128)))
        for block in (old['stages'][0], old['lead']):
            self.assertFalse({'cut', 'seat_other', 'power_other', 'cut_other'} & set(block))
        self.assertNotIn('blind', old)
        new = resolved(dict(stages=[dict(mode='rollout', from_trick=1, seat='top', seat_other='draw', cut_other=.25)], blind=True,
                            names={'self': 'a', '*': '', 'they_see': ''}))
        self.assertEqual((new['stages'][0]['seat_other'], new['stages'][0]['cut_other'], new['blind']), ('draw', .25, True))
        self.assertNotIn('cut', new['stages'][0])
        self.assertEqual(new['names']['they_see'], '')
        for bad in (dict(stages=[dict(seat_other='deep')]), dict(stages=[dict(cut=1.)]), dict(stages=[dict(cut_other=-.1)]), dict(blind=1)):
            with self.assertRaises(ValueError):
                resolved(bad)

    def test_bad_settings_are_refused(self):
        for block in (dict(stages=[dict(mode='deep')]), dict(stages=[dict(from_trick=5, to_trick=4)]), dict(stages=[dict(nonsense=1)]),
                      dict(stages=[dict(from_trick=3, to_trick=6), dict(from_trick=6, to_trick=9)]), dict(claims=dict(cards=14)),
                      dict(capture=dict(level=3)), dict(mix=dict(near=-1)), dict(other=1), dict(stages=[dict(mode='rollout', layouts=0)]),
                      dict(stages=[dict(mode='blend', objective='imps')]), dict(others=[dict(policy='x', share=1.5)]),
                      dict(capture=dict(mix_share=1.5)), dict(mix=dict(defender_power=-1)), dict(stages=[dict(contracts='slams')])):
            with self.assertRaises(ValueError, msg=str(block)):
                x8_settings(block)


class PieceTests(unittest.TestCase):
    def test_touching_cards_are_one_run_until_a_live_card_comes_between(self):
        # North to lead holds S AKQ 9 8 and H 5 4 2; the S T and H 3 have gone in earlier tricks, the S J is still out.
        n = [card(x) for x in 'SA SK SQ S9 S8 H5 H4 H2 D2 D3 D4 D5 D6'.split()]
        rest = [x for x in range(52) if x not in n]
        e, s, w = rest[0::3][:13], rest[1::3][:13], rest[2::3][:13]
        board = Board('t', tuple(tuple(sorted(h)) for h in (n, e, s, w)), Contract(3, 'N', 3), 0, 'None', ())
        game = Game(board)
        o = game.observation()
        runs = [[symbol(x) for x in run] for run in touching(o)]
        self.assertIn(['SQ', 'SK', 'SA'], runs)
        self.assertIn(['S8', 'S9'], runs)
        self.assertIn(['H4', 'H5'], runs)             # the H3 is live in another hand: the H2 is its own run
        self.assertIn(['H2'], runs)
        holder = np.full(52, 1, np.int8)
        holder[n] = 0
        dead = np.zeros(52, bool)
        dead[card('ST')] = True
        self.assertEqual(runs_with(holder, dead, 0, card('S9')), {card('S8'), card('S9')})
        dead[card('SJ')] = True                       # with the jack gone too the run reaches the honours
        holder[card('SJ')] = -1
        holder[card('ST')] = -1
        self.assertEqual(runs_with(holder, dead, 0, card('S9')), {card(x) for x in ('S8', 'S9', 'SQ', 'SK', 'SA')})

    def test_worth_counts_tricks_or_imps_from_the_deciders_side(self):
        _, o, _ = spot(1, 5)
        declaring = o.controller % 2 == o.contract.declarer % 2
        t = np.array([[9, 8], [7, 10]])
        np.testing.assert_array_equal(worth(t, o, 'tricks'), t if declaring else -t)
        got = worth(t, o, 'imps', 0)
        np.testing.assert_array_equal(got[:, 0], [0., 0.])
        self.assertEqual(np.sign(got[0, 1]), -1 if declaring else 1)      # one trick fewer for declarer
        self.assertEqual(np.sign(got[1, 1]), 1 if declaring else -1)

    def test_paired_standard_error(self):
        u = np.array([[1., 0.], [1., 1.], [1., 0.], [1., 1.]])
        mean, se = paired(u, np.ones(4), 0)
        np.testing.assert_allclose(mean, [0., .5])
        self.assertEqual(se[0], 0.)
        self.assertAlmostEqual(se[1], np.sqrt(.25 * 4 / 3 / 4))


class RolloutTests(Fixture8):
    def test_the_batch_takes_what_card_by_card_playouts_take(self):
        p = self.make()
        for seed in range(6):
            _, o, world = spot(seed, 5 + 5 * seed)
            rng = random.Random(seed)
            worlds = [world] + [shuffled(o, world, rng) for _ in range(4)]
            cards = list(o.legal)[:3]
            want = card_values(o, worlds, cards, NetPlayer(p.net, 'top'), Public(p.net, o))
            got = evaluate(o, worlds, cards, Seats([p.net]).start(o))
            declaring = o.controller % 2 == o.contract.declarer % 2
            np.testing.assert_array_equal(got.tricks if declaring else -got.tricks, want, err_msg=f'seed {seed}')
            self.assertFalse(got.floor.any())
            self.assertTrue((got.ended < 0).all())
            self.assertGreater(got.net_rows, 0)

    def test_a_horizon_stops_and_solves(self):
        p = self.make()
        _, o, world = spot(3, 10)
        cards = list(o.legal)[:2]
        want = card_values(o, [world], cards, NetPlayer(p.net, 'top'), Public(p.net, o), tricks=2, dds=p.dds)
        got = evaluate(o, [world], cards, Seats([p.net]).start(o), horizon=2, dds=p.dds)
        declaring = o.controller % 2 == o.contract.declarer % 2
        np.testing.assert_array_equal(got.tricks if declaring else -got.tricks, want)

    def test_another_net_plays_the_other_side_where_the_layout_says_so(self):
        """With a second net for the other side in layout 1 only, layout 0's rollouts are unchanged, and layout 1's are
        what that net alone would give when the two nets are told apart by a flipped preference."""
        p = self.make()
        from bridge_harness.gen7_net import PolicyNet
        other = PolicyNet(self.root / 'gen7.npz', p.scorer)
        other.params = dict(other.params)
        for k, v in other.params.items():               # the same net with its policy turned upside down
            if k in ('wd1',):
                other.params[k] = -v
        differ = 0
        for seed in range(6):
            _, o, world = spot(seed, 9 + 3 * seed)
            cards = list(o.legal)[:2]
            alone = evaluate(o, [world, world], cards, Seats([p.net]).start(o))
            mixed = evaluate(o, [world, world], cards, Seats([p.net, other]).start(o), other=[0, 1])
            np.testing.assert_array_equal(mixed.tricks[0], alone.tricks[0])
            differ += int((mixed.lines[1::2] != alone.lines[1::2]).any())
        self.assertGreater(differ, 2)

    def test_a_net_that_takes_who_is_playing_is_told_each_rows_side(self):
        """With a rollout net that has bot vectors, every row's choice is the net's on that row with the side to play's
        bot as `bot_own` and the other side's as `bot_other`; unknown names are row 0."""
        from bridge_harness.gen7_net import PolicyNet, forward, log_softmax
        from bridge_harness.plan_rollout import inputs
        p = self.make()
        with np.load(self.root / 'gen7.npz') as z:
            params = {k: z[k] for k in z.files}
        width = params['bt0'].shape[0]
        r = np.random.default_rng(3)
        params.update(emb_own=(2 * r.standard_normal((3, width))).astype(np.float32), emb_other=(2 * r.standard_normal((3, width))).astype(np.float32),
                      bot_vocab=np.array(['?', 'me', 'them']))
        np.savez(self.root / 'who.npz', **params)
        net = PolicyNet(self.root / 'who.npz', p.scorer)
        self.assertEqual((net.bot_id('me'), net.bot_id('them'), net.bot_id('nobody')), (1, 2, 0))
        told = 0
        for seed in range(6):
            _, o, world = spot(seed, 9 + 4 * seed)
            rng = random.Random(seed)
            worlds = [world] + [shuffled(o, world, rng) for _ in range(3)]
            for who, ids in ((('me', 'them'), (1, 2)), (('me', 'nobody'), (1, 0))):
                seats = Seats([net], who=who).start(o)
                rows = Rows(o, worlds)
                rows.play(np.full(rows.n, o.legal[0]))
                while not rows.done:
                    got, free, _ = seats.cards(rows)
                    if len(free):
                        b = {k: v[free] for k, v in inputs(rows, seats.publics[0]).items()}
                        mine = rows.controller()[free] % 2 == o.controller % 2
                        b['bot_own'] = np.where(mine, ids[0], ids[1])
                        b['bot_other'] = np.where(mine, ids[1], ids[0])
                        want = log_softmax(forward(net.params, b)['policy']).argmax(axis=1)
                        np.testing.assert_array_equal(got[free], want)
                        told += len(free)
                    rows.play(got)
        self.assertGreater(told, 100)

    def test_the_other_side_can_take_its_cards_another_way(self):
        """`other`: the deciding side's seats play by the seats' own settings, the other side's by `other`; a `cut` keeps a
        draw among the cards at least that share as likely as the likeliest; `seen` is what the other side is told about
        the deciding side's bot. With neither `other` nor a cut the cards are what they always were."""
        from bridge_harness.gen7_net import PolicyNet, forward, log_softmax
        from bridge_harness.plan_rollout import inputs
        p = self.make()
        with np.load(self.root / 'gen7.npz') as z:
            params = {k: z[k] for k in z.files}
        width = params['bt0'].shape[0]
        r = np.random.default_rng(4)
        params.update(emb_own=(2 * r.standard_normal((3, width))).astype(np.float32), emb_other=(2 * r.standard_normal((3, width))).astype(np.float32),
                      bot_vocab=np.array(['?', 'me', 'them']))
        np.savez(self.root / 'who2.npz', **params)
        net = PolicyNet(self.root / 'who2.npz', p.scorer)
        own_rows = other_rows = off_top = 0
        for seed in range(6):
            _, o, world = spot(seed, 9 + 4 * seed)
            rng = random.Random(seed)
            worlds = [world] + [shuffled(o, world, rng) for _ in range(5)]
            plain, split = Seats([net], 'draw', seed=seed, who=('me', 'them')).start(o), \
                Seats([net], 'top', seed=seed, who=('me', 'them'), seen='nobody', other=dict(mode='draw', cut=.5)).start(o)
            same = Seats([net], 'draw', seed=seed, who=('me', 'them'), other=None, cut=0.).start(o)
            rows = Rows(o, worlds)
            rows.play(np.full(rows.n, o.legal[0]))
            while not rows.done:
                first, free, _ = plain.cards(rows)
                np.testing.assert_array_equal(first, same.cards(rows)[0])       # the same seed, the same draws: nothing moved
                got, free2, logp = split.cards(rows)
                np.testing.assert_array_equal(free, free2)
                if len(free):
                    b = {k: v[free] for k, v in inputs(rows, split.publics[0]).items()}
                    mine = rows.controller()[free] % 2 == o.controller % 2
                    b['bot_own'] = np.where(mine, 1, 2)
                    b['bot_other'] = np.where(mine, 2, 0)                        # the other side is told nothing about this bot
                    want = log_softmax(forward(net.params, b)['policy'])
                    np.testing.assert_allclose(logp, want, rtol=1e-5, atol=1e-5)
                    legal = rows.legal()[free]
                    top = np.where(legal, want, -np.inf).argmax(axis=1)
                    np.testing.assert_array_equal(got[free][mine], top[mine])   # its own side: the likeliest card
                    pick = want[np.arange(len(free)), got[free]]
                    self.assertTrue(legal[np.arange(len(free)), got[free]].all())
                    self.assertTrue((np.exp(pick[~mine]) >= .5 * np.exp(want.max(axis=1)[~mine]) - 1e-6).all())    # the others: drawn, within the cut
                    own_rows += int(mine.sum()); other_rows += int((~mine).sum()); off_top += int((got[free][~mine] != top[~mine]).sum())
                rows.play(first)
        self.assertGreater(own_rows, 50)
        self.assertGreater(other_rows, 50)
        self.assertGreater(off_top, 0)              # the other side's cards are drawn: not always its likeliest

    def test_a_blind_bot_is_told_nothing_about_its_opponent(self):
        """`blind`: whoever sits against the bot, every setting keyed by the opponent's id takes its '*' value."""
        settings = dict(names={'self': 'me', 'known': 'them', '*': ''}, mix=dict(read_declarer=['known']), claims=dict(opponents=['known']))
        weights = dict(opponent_play_weight={'known': 1., '*': .3})
        told, blind = self.make8(x8=settings, gen7=weights), self.make8(x8=dict(settings, blind=True), gen7=weights)
        for p in (told, blind):
            p.meet('known')
        self.assertEqual((told.opponent_id, told.opponent_factor), ('known', 1.))
        self.assertEqual((blind.opponent_id, blind.opponent_factor), (None, .3))
        _, o, _ = spot(1, 9)
        if o.controller % 2 == o.contract.declarer % 2:      # a defender's view: the declarer is the opponent whose cards are read
            _, o, _ = spot(1, 10)
        self.assertEqual(o.contract.declarer in told.mixers(o), o.controller % 2 != o.contract.declarer % 2)
        self.assertNotIn(o.contract.declarer, blind.mixers(o))

    def test_a_blind_bot_is_told_a_variable_populations_identifier(self):
        """A variable-personality population's identifier names no persona, so a blind bot is told it (persona.KNOWN or the
        spec's `variable_ids`), unless `read_variable` is off."""
        blind = self.make8(x8=dict(blind=True))
        for who, seen in (('SidVariable', 'SidVariable'), ('stu4c-put', None), (None, None)):
            blind.meet(who)
            self.assertEqual(blind.opponent_id, seen)
        off = self.make8(x8=dict(blind=True, read_variable=False))
        off.meet('SidVariable')
        self.assertIsNone(off.opponent_id)
        self.assertEqual(resolved(dict(read_variable=False)).get('read_variable'), False)
        self.assertNotIn('read_variable', resolved({}))
        own = self.make8(x8=dict(blind=True))
        own.spec['variable_ids'] = ['g8-variable']
        own.meet('g8-variable')
        self.assertEqual(own.opponent_id, 'g8-variable')

    def test_forks_replay_to_their_seat_and_their_results(self):
        p = self.make()
        seen = 0
        for seed in range(5):
            _, o, world = spot(seed, 6 + 4 * seed)
            rng = random.Random(seed)
            worlds = [world] + [shuffled(o, world, rng) for _ in range(3)]
            cards = list(o.legal)[:2]
            got = evaluate(o, worlds, cards, Seats([p.net]).start(o), forks=6, rng=np.random.default_rng(seed))
            for f in got.forks:
                row = x8_capture.fork_row(o, worlds[f.layout], f)
                json.dumps(row)
                view, main, alt, main_tricks, other_tricks, p_main, p_other = x8_capture.fork_view(o, row)
                self.assertEqual(view.actor, f.seat)
                self.assertIn(main, view.legal)
                self.assertIn(alt, view.legal)
                self.assertNotEqual(main, alt)
                self.assertNotIn(alt, [x for run in touching(view) if main in run for x in run])       # a different job, not a touching card
                self.assertEqual(main, max(view.legal, key=lambda x: float(p.net.log_policy([view])[0][x])))
                self.assertAlmostEqual(p_main, float(np.exp(p.net.log_policy([view])[0][main])), places=3)
                # each line played on by the net, one row at a time, takes what the pair says
                for first, want in ((main, main_tricks), (alt, other_tricks)):
                    hands = x8_capture.imagined_board(o, worlds[f.layout]).hands
                    game = Game(Board('f', hands, o.contract, o.dealer, o.vulnerability, o.auction))
                    for x in [y for _, y in o.history] + [f.first, *f.prefix, first]:
                        game.play(x)
                    while not game.done:
                        now = game.observation()
                        logp = p.net.log_policy([now])[0]
                        game.play(max(now.legal, key=lambda x: (float(logp[x]), -x)) if len(now.legal) > 1 else now.legal[0])
                    self.assertEqual(game.declarer_tricks, want)
                self.assertEqual(main_tricks, int(got.tricks[f.layout, cards.index(f.first)]))
                seen += 1
        self.assertGreater(seen, 12)

    def test_layouts_and_results_round_trip(self):
        for seed in range(4):
            _, o, world = spot(seed, 7 + 6 * seed)
            rng = random.Random(seed)
            worlds = [shuffled(o, world, rng) for _ in range(5)]
            for w in worlds:
                self.assertEqual(x8_capture.layout_world(o, x8_capture.layout_code(o, w)), w)
            tricks = np.arange(10, dtype=np.int16).reshape(5, 2) - 1
            floor = tricks % 2 == 0
            weights = np.array([.1, .4, .2, .05, .25])
            cap = x8_capture.capture_block(o, worlds, weights, tricks, floor, 3)
            json.dumps(cap)
            got_worlds, got_w, got_t, got_f = x8_capture.read_capture(o, cap)
            order = [1, 4, 2]
            self.assertEqual(got_worlds, [worlds[i] for i in order])
            np.testing.assert_allclose(got_w, weights[order], rtol=1e-6)
            np.testing.assert_array_equal(got_t, tricks[order])
            np.testing.assert_array_equal(got_f, floor[order])
        self.assertEqual(x8_capture.text_cards(x8_capture.cards_text(range(52))), list(range(52)))


class PlayerTests(Fixture8):
    GEN8 = dict(play_weight=1., early_play_weight=1., early_pool=32, early_min_effective=4.)

    def test_with_nothing_switched_on_it_plays_gen7s_game_card_for_card(self):
        seven = self.make(Gen7Player, gen7=self.GEN8, list_solve=16)
        eight = self.make8({}, gen7=self.GEN8, list_solve=16)
        compared = 0
        for seed in (2, 3):
            board = next(generate(1, 700 + seed))
            for room in (0, 1):
                a, b = self.table(seven, board, room), self.table(eight, board, room)
                self.assertEqual([x['card'] for x in a['actions']], [x['card'] for x in b['actions']])
                for x, y in zip(a['actions'], b['actions']):
                    if x['player'] == 'x' and 'gen6' in x:
                        self.assertEqual(x['estimates'], y['estimates'])
                        self.assertEqual(x['behavior_probabilities'], y['behavior_probabilities'])
                        self.assertNotIn('x8', y)
                        compared += 1
        self.assertGreater(compared, 40)

    def test_a_blend_stage_and_a_tree_stage_may_not_share_a_trick(self):
        with self.assertRaises(ValueError):
            self.make8(dict(stages=[dict(from_trick=3, to_trick=6, mode='blend')]), gen7=dict(tree=dict(from_trick=5, to_trick=7)))
        self.make8(dict(stages=[dict(from_trick=3, to_trick=4, mode='blend')]), gen7=dict(tree=dict(from_trick=5, to_trick=7)))

    def test_full_tables_with_rollouts_and_the_blend(self):
        x8 = dict(stages=[dict(from_trick=2, to_trick=4, mode='blend', trust=.5, layouts=12, cards=3, margin=2.),
                          dict(from_trick=5, to_trick=6, mode='blend', trust=.5, layouts=0, cards=3, margin=2.),
                          dict(from_trick=7, to_trick=13, mode='rollout', layouts=24, first=8, cards=3, prior=.01)],
                  capture=dict(level=2, forks=4, layouts=8))
        p = self.make8(x8, gen7=self.GEN8, list_solve=16)
        modes, forks, raced = dict(rollout=0, blend=0), 0, 0
        for seed in (2, 3):
            board = next(generate(1, 700 + seed))
            for room in (0, 1):
                for a, o in self.views(board, self.table(p, board, room)):
                    note = a.get('x8')
                    if a['player'] != 'x' or not note:
                        continue
                    self.assertAlmostEqual(sum(a['behavior_probabilities'].values()), 1., places=9)
                    self.assertGreater(a['behavior_probabilities'][a['card']], 0.)
                    self.assertEqual(note['trick'], a['ply'] // 4 + 1)
                    if note['mode'] == 'rollout':
                        self.assertNotIn('estimates', a)                  # nothing was solved: no search estimates to record
                        self.assertEqual(a['dds_calls'], 0)
                        self.assertIn(a['card'], [x for j in note['alive'] for x in note['runs'][j]])
                        if note['n'][0]:
                            self.assertLessEqual(max(note['n']), note['layouts'])
                            if len(note['alive']) > 1:                  # several survivors: each got every layout
                                self.assertEqual({note['n'][j] for j in note['alive']}, {note['layouts']})
                            else:                                       # one survivor: the race ended when the last rival fell
                                self.assertEqual(note['n'][note['alive'][0]], max(note['n']))
                            raced += min(note['n']) < note['layouts']
                            best = max(note['value'][j] for j in note['alive'])
                            self.assertAlmostEqual(note['value'][[j for j in note['alive'] if a['card'] in note['runs'][j]][0]], best, places=6)
                    else:
                        self.assertIn('estimates', a)
                        if note.get('consulted'):
                            self.assertEqual(a['gen7_tree']['kind'], 'x8')
                            self.assertIn(a['card'], note['kept'])
                            for s, r, v in zip(note['search'], note['roll'], note['value']):
                                self.assertAlmostEqual(v, .5 * s + .5 * r, places=3)
                            self.assertEqual(note['fresh'], note['trick'] <= 4)
                    if note.get('n') and note['n'][0]:
                        modes[note['mode']] += 1
                        worlds, w, tricks, floor = x8_capture.read_capture(o, note['cap'])
                        self.assertEqual(tricks.shape, (len(worlds), len(note['cards'])))
                        self.assertLessEqual(len(worlds), 8)
                        self.assertFalse(floor.any())
                        for world in worlds:                                # a layout holds the decider's own cards and dummy as they are
                            self.assertEqual(world[o.controller], o.known_hands[o.controller])
                            self.assertEqual(world[o.contract.dummy], o.known_hands[o.contract.dummy])
                        for row in note['forks']:
                            view = x8_capture.fork_view(o, row)[0]
                            self.assertEqual(view.history[:len(o.history)], o.history)
                            forks += 1
        self.assertGreater(modes['rollout'], 8)
        self.assertGreater(modes['blend'], 4)
        self.assertGreater(forks, 20)

    def test_a_race_of_zero_plays_every_candidate_on_every_layout(self):
        x8 = dict(stages=[dict(from_trick=4, to_trick=13, mode='rollout', layouts=16, first=4, cards=4, prior=0., race=0.)], capture=dict(level=0))
        p = self.make8(x8, gen7=self.GEN8, list_solve=16)
        board = next(generate(1, 702))
        seen = 0
        for a in self.table(p, board, 0)['actions']:
            note = a.get('x8')
            if a['player'] == 'x' and note and note.get('rounds'):
                self.assertEqual(len(note['rounds']), 1)
                self.assertEqual(set(note['n']), {note['layouts']})
                self.assertNotIn('forks', note)
                self.assertNotIn('cap', note)
                seen += 1
        self.assertGreater(seen, 4)

    def test_a_persona_seat_chooses_by_its_style_within_its_margin(self):
        """`table_styles`: a seat's persona at this table picks among the candidates within its margin by its style; seats
        without one, and the bot without any, play as before."""
        x8 = dict(stages=[dict(from_trick=8, to_trick=13, mode='rollout', layouts=12, first=4)])
        plain, styled = self.make8(x8, gen7=self.GEN8, list_solve=16), self.make8(x8, gen7=self.GEN8, list_solve=16)
        styled.table_styles = {s: {'play': {'high': 1., 'random': 0.}, 'near': 0.6} for s in range(4)}
        moved = narrowed = 0
        for seed in (2, 3, 4):
            board = next(generate(1, 700 + seed))
            for room in (0, 1):
                a_plain = self.table(plain, board, room)['actions']
                a_styled = self.table(styled, board, room)['actions']
                for a in a_plain:
                    self.assertNotIn('styled', a.get('x8', {}))
                for a in a_styled:
                    note = a.get('x8') or {}
                    if 'styled' in note:
                        narrowed += 1
                        values = [note['value'][note['cards'].index(c)] for c in note['styled']]
                        self.assertLessEqual(max(values) - min(values), 0.6 + 1e-6)      # the near-equal set, within the margin
                        self.assertIn(a['card'], [x for c in note['styled'] for x in note['runs'][note['cards'].index(c)]])
                moved += [x['card'] for x in a_plain] != [x['card'] for x in a_styled]
        self.assertGreater(narrowed, 0)
        self.assertGreater(moved, 0)

    def test_a_mixing_declarer_plays_its_equal_cards_alike_and_a_defender_does_not(self):
        x8 = dict(stages=[dict(from_trick=8, to_trick=13, mode='rollout', layouts=12, first=4)], mix=dict(declarer=True))
        p = self.make8(x8, gen7=self.GEN8, list_solve=16)
        mixed = plain = 0
        for seed in (2, 3, 4):
            board = next(generate(1, 700 + seed))
            for room in (0, 1):
                for a, o in self.views(board, self.table(p, board, room)):
                    if a['player'] != 'x' or 'behavior_probabilities' not in a:
                        continue
                    live = [q for q in a['behavior_probabilities'].values() if q > 0]
                    if len(live) < 2:
                        continue
                    if o.controller % 2 == o.contract.declarer % 2:
                        self.assertEqual(len(set(round(q, 12) for q in live)), 1)
                        self.assertTrue(a.get('selector', '').startswith('x8-mix') or a['x8']['mixed'])
                        mixed += 1
                    else:
                        plain += 1
        self.assertGreater(mixed, 5)

    def test_with_a_power_equal_cards_are_mixed_as_the_nets_probability_to_that_power(self):
        x8 = dict(stages=[dict(from_trick=8, to_trick=13, mode='rollout', layouts=12, first=4)], mix=dict(declarer=True, declarer_power=2.))
        p = self.make8(x8, gen7=self.GEN8, list_solve=16)
        seen = uneven = 0
        for seed in (2, 3, 4):
            board = next(generate(1, 700 + seed))
            for room in (0, 1):
                for a, o in self.views(board, self.table(p, board, room)):
                    if a['player'] != 'x' or 'behavior_probabilities' not in a or o.controller % 2 != o.contract.declarer % 2:
                        continue
                    live = {k: q for k, q in a['behavior_probabilities'].items() if q > 0}
                    if len(live) < 2:
                        continue
                    lp = p.net.log_policy([o])[0].astype(np.float64)
                    w = {k: np.exp(2. * lp[card(k)]) for k in live}
                    for k in live:
                        self.assertAlmostEqual(live[k], w[k] / sum(w.values()), places=5)
                    seen += 1
                    uneven += max(live.values()) - min(live.values()) > .05
        self.assertGreater(seen, 5)
        self.assertGreater(uneven, 0)

    def test_a_mixers_card_is_read_as_its_run_of_touching_cards(self):
        """For every hidden chooser's play, the pooled probability in a layout is the net's probability of the run of
        touching cards (taken in the hand that played, as that layout has it) divided by the run's length, computed
        here from each layout's own Observation (with a power, shared out as p ** power over the run); and with no
        mixer listed the reading is Gen7Player's."""
        from bridge_harness.gen7 import hidden_plays, past_view
        plain = self.make(Gen7Player, gen7=self.GEN8, list_solve=16)
        quiet = self.make8({}, gen7=self.GEN8, list_solve=16)
        for power in (0., 2.):
            self.check_reading(plain, quiet, power)

    def check_reading(self, plain, quiet, power):
        from bridge_harness.gen7 import hidden_plays, past_view
        mixing = self.make8(dict(mix=dict(read_declarer=['*'], read_defender=['*'], defender=True, declarer_power=power,
                                          defender_power=power)), gen7=self.GEN8, list_solve=16)
        checked = pooled = 0
        for seed in range(8):
            _, o, world = spot(seed, 14 + 3 * seed)
            view = View(o)
            assign = view.uniform(6, np.random.default_rng(seed))
            assign[0] = np.array([view.hidden.index(next(s for s in view.hidden if c in world[s])) for c in view.unseen])
            np.testing.assert_allclose(quiet.play_log_likelihood(o, view, assign), plain.play_log_likelihood(o, view, assign))
            plays = hidden_plays(o)
            logp, options = mixing.play_log_probabilities(o, view, assign, plays)
            mixers = mixing.mixers(o)
            for k, (i, seat, chooser) in enumerate(plays):
                for row in range(len(assign)):
                    held = mixing.held_then(o, view, assign[row:row + 1], i, chooser)[0]
                    hand = set(np.flatnonzero(held)) if seat == chooser else set(o.original_hand(seat)) - {x for s, x in o.history[:i] if s == seat}
                    v = past_view(o, i, sorted(np.flatnonzero(held)))
                    if len(v.legal) < 2:
                        self.assertEqual(logp[k, row], 0.)
                        continue
                    lp = mixing.net.log_policy([v])[0].astype(np.float64)
                    x = o.history[i][1]
                    if chooser in mixers:
                        dead = {y for _, y in o.history[:i - i % 4]}
                        run = {x}
                        for step in (1, -1):
                            y = x + step
                            while 0 <= y < 52 and y // 13 == x // 13 and (y in hand or y in dead):
                                if y in hand:
                                    run.add(y)
                                y += step
                        want = np.log(sum(np.exp(lp[y]) for y in run)) - np.log(len(run))
                        if power:
                            want = np.log(sum(np.exp(lp[y]) for y in run)) + power * lp[x] - np.log(sum(np.exp(power * lp[y]) for y in run))
                        pooled += len(run) > 1
                    else:
                        want = lp[x]
                    self.assertAlmostEqual(logp[k, row], want, places=4, msg=f'seed {seed} play {i}')
                    self.assertEqual(options[k, row], len(v.legal))
                    checked += 1
        self.assertGreater(checked, 200)
        self.assertGreater(pooled, 20)

    def test_factory(self):
        self.assertIs(type(self.make8({})), X8Player)
        with patch('bridge_harness.gen6.BidderState', FakeState), patch('bridge_harness.mixed_arena.Weights', FakeBelief):
            spec = dict(self.make8({}).spec)
            a = player(spec, self.root)
            b = player(dict(spec, engine='gen7'), self.root)
        self.players += [a, b]
        self.assertIs(type(a), X8Player)
        self.assertIs(type(b), Gen7Player)


class SolverProcessTests(unittest.TestCase):
    """The process wrapper, against a stand-in solver that answers at once or not at all."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.fake = Path(self.dir.name) / 'fake_solver'
        self.fake.write_text(f"#!{sys.executable}\n" + '''
import sys, time
for line in sys.stdin:
    if 'slow' in line:
        time.sleep(30)
    print('{"left": 2, "cards": {"5": 1, "6": 0}}' if line.startswith('N') else '{"left": 2, "value": 1}', flush=True)
''')
        self.fake.chmod(self.fake.stat().st_mode | stat.S_IEXEC)

    def tearDown(self):
        self.dir.cleanup()

    def test_answers_are_remembered_and_a_slow_question_is_abandoned(self):
        s = x8_claims.Solver(str(self.fake))
        try:
            a = s.ask(['N1 a', 'b', 'N1 a'])
            self.assertEqual(a[0], dict(cards={5: 1, 6: 0}, left=2))
            self.assertEqual(a[1], dict(value=1, left=2))
            self.assertIs(a[0], a[2])
            self.assertEqual(s.calls, 2)
            got = s.ask(['N1 c', 'slow', 'N1 d'], allowance=.4, each=.2)
            self.assertIsNotNone(got[0])
            self.assertIsNone(got[1])
            self.assertIsNone(got[2])
            self.assertEqual(s.timeouts, 1)
            self.assertIsNotNone(s.ask(['N1 d'])[0])                # a new process answers
            self.assertEqual(s.ask(['N1 a'])[0], a[0])
            self.assertEqual(s.hits, 1)
        finally:
            s.close()

    def test_a_missing_solver_is_an_error_at_once(self):
        with self.assertRaises(RuntimeError):
            x8_claims.Finder(str(Path(self.dir.name) / 'nothing'))

    def test_holds(self):
        self.assertTrue(x8_claims.holds(dict(cards={1: 0, 2: 1}), True))
        self.assertFalse(x8_claims.holds(dict(cards={1: 0, 2: 1}), False))
        self.assertTrue(x8_claims.holds(dict(cards={1: 1, 2: 1}), False))
        self.assertFalse(x8_claims.holds(dict(cards={}), True))


def random_board(seed):
    rng = random.Random(seed)
    deck = list(range(52))
    rng.shuffle(deck)
    hands = tuple(tuple(sorted(deck[13 * s:13 * s + 13])) for s in range(4))
    return Board(f'b{seed}', hands, Contract(rng.randint(1, 6), rng.choice('SHDCN'), rng.randrange(4)), 0, 'None', ())


@unittest.skipUnless(HAVE_SOLVER, 'SURE_BIN is not set to a built sure_cpp')
class ClaimTests(Fixture8):
    def test_the_three_questions_against_the_game_and_the_first_wrapper(self):
        finder, old = x8_claims.Finder(BIN), claims.Claims(BIN)
        seen = dict(root=0, after=0, boundary=0)
        try:
            for seed in range(25):
                b = random_board(seed)
                g, rng, c = Game(b), random.Random(seed), b.contract
                while not g.done:
                    o = g.observation()
                    left = len(g.hands[o.actor])
                    declaring = o.actor % 2 == c.declarer % 2
                    world = tuple(tuple(sorted(h)) for h in g.hands)
                    if left <= 7 and o.history and declaring:
                        state, text = x8_claims.root_line(o)
                        if state == 'ask':                              # the same position the first wrapper builds
                            self.assertEqual(text, 'N%d %s' % (c.level + 6 - o.declarer_tricks, claims.position(o)))
                        got, sure = finder.root(o)
                        want, value = old.verdict(o)
                        self.assertEqual(got, want)
                        if got in ('guaranteed', 'open'):
                            need = c.level + 6 - o.declarer_tricks
                            self.assertEqual(sure, {x: value[x] >= need for x in o.legal})
                        seen['root'] += 1
                    if left <= 7 and o.history and not declaring:
                        for x in o.legal:                               # after each card: the position the game then shows declarer
                            state, text, declaring_next = x8_claims.after_card(o, world, x)
                            g2 = Game(b)
                            for _, y in o.history:
                                g2.play(y)
                            g2.play(x)
                            need = c.level + 6 - g2.declarer_tricks
                            if need <= 0:
                                self.assertEqual(state, 'made')
                            elif g2.done or need > 13 - len(g2.history) // 4:
                                self.assertEqual(state, 'lost')
                            else:
                                o2 = g2.observation()
                                self.assertEqual(state, 'ask')
                                self.assertEqual(declaring_next, o2.actor % 2 == c.declarer % 2)
                                if declaring_next:
                                    self.assertEqual(text, 'N%d %s' % (need, claims.position(o2)))
                                seen['after'] += 1
                    if not g.trick and 0 < left <= 6 and o.history:
                        sure, n = finder.boundaries(Rows(o, [world, world]), [1])
                        self.assertEqual((n, len(sure)), (left, 1))
                        if declaring:                                   # a position's value is its best card's
                            self.assertEqual(int(sure[0]), max(old.values(o).values()))
                        seen['boundary'] += 1
                    g.play(rng.choice(o.legal))
        finally:
            finder.close()
            old.close()
        self.assertGreater(min(seen.values()), 100)

    def test_a_hand_over_is_a_guarantee_declarer_did_not_have_to_find(self):
        """Where a defender's card hands declarer a guarantee in the true layout, declarer's next decision (if the
        declaring side plays next) is 'guaranteed' by the root question; where it does not, it is not."""
        finder = x8_claims.Finder(BIN)
        yes = no = 0
        try:
            for seed in range(40):
                b = random_board(100 + seed)
                g, rng, c = Game(b), random.Random(seed), b.contract
                while not g.done:
                    o = g.observation()
                    if o.history and o.actor % 2 != c.declarer % 2 and len(g.hands[o.actor]) <= 6:
                        world = tuple(tuple(sorted(h)) for h in g.hands)
                        cards = list(o.legal)
                        hand = finder.handovers(o, [world], cards)
                        for j, x in enumerate(cards):
                            g2 = Game(b)
                            for _, y in o.history:
                                g2.play(y)
                            g2.play(x)
                            if g2.done:
                                continue
                            o2 = g2.observation()
                            if o2.actor % 2 == c.declarer % 2:
                                state, _ = finder.root(o2)
                                self.assertEqual(int(hand[0, j]), int(state in ('guaranteed', 'made')), (seed, symbol(x), state))
                                yes += hand[0, j] == 1
                                no += hand[0, j] == 0
                    g.play(rng.choice(o.legal))
        finally:
            finder.close()
        self.assertGreater(yes, 20)
        self.assertGreater(no, 20)

    def test_rollouts_end_where_every_trick_is_claimed(self):
        # North holds the top cards of three suits and the club ace: thirteen tricks at notrump whatever is led.
        hand = lambda text: tuple(sorted(card(x) for x in text.split()))
        n = hand('SA SK SQ SJ HA HK HQ HJ DA DK DQ DJ CA')
        e = hand('S2 S3 S4 S5 H2 H3 H4 H5 D2 D3 D4 D5 C2')
        s = hand('S6 S7 S8 S9 H6 H7 H8 H9 D6 D7 D8 D9 C3')
        w = hand('ST HT DT CK CQ CJ CT C9 C8 C7 C6 C5 C4')
        game = Game(Board('t', (n, e, s, w), Contract(3, 'N', 0), 0, 'None', ()))
        game.play(card('C2'))
        o = game.observation()                                          # dummy (South) to play to the first trick
        p = self.make()
        finder = x8_claims.Finder(BIN)
        try:
            world = tuple(tuple(sorted(h)) for h in game.hands)
            plain = evaluate(o, [world], list(o.legal)[:2], Seats([p.net]).start(o))
            got = evaluate(o, [world], list(o.legal)[:2], Seats([p.net]).start(o), finder=finder, target=9, leaf_cards=13)
            self.assertTrue((got.ended >= 0).all())
            np.testing.assert_array_equal(got.tricks, 13)
            self.assertTrue(got.floor.all())
            self.assertLess(got.net_rows, plain.net_rows)
            skipped = evaluate(o, [world], list(o.legal)[:2], Seats([p.net]).start(o), finder=finder, target=9, leaf_cards=13,
                               ask=np.zeros((1, 2), bool))
            np.testing.assert_array_equal(skipped.tricks, plain.tricks)  # rows that are not asked play on as they would
            self.assertEqual(skipped.asked, 0)
        finally:
            finder.close()

    def test_a_declarer_that_holds_a_guarantee_keeps_it_and_makes(self):
        x8 = dict(stages=[dict(from_trick=4, to_trick=6, mode='blend', trust=.5, layouts=8, margin=3.),
                          dict(from_trick=7, to_trick=13, mode='rollout', layouts=12, first=4, prior=0.)],
                  claims=dict(cards=8, defender=6, leaf=5, contracts='all'), capture=dict(level=0), mix=dict(declarer=True))
        p = self.make8(x8, gen7=self.GEN8, list_solve=16)
        check = x8_claims.Finder(BIN)
        kept = moved = odds = 0
        try:
            for seed in range(8):
                board = next(generate(1, 800 + seed))
                target = board.contract.level + 6
                for room in (0, 1):
                    result = self.table(p, board, room)
                    held = False
                    for a, o in self.views(board, result):
                        note = a.get('x8')
                        if a['player'] != 'x' or not note:
                            continue
                        if note.get('odds'):
                            self.assertTrue(all(0 <= q <= 1 for q in note['odds']))
                            odds += 1
                        if note.get('claim') == 'guaranteed':
                            state, sure = check.root(o)
                            self.assertEqual(state, 'guaranteed')
                            self.assertTrue(sure[card(a['card'])], (seed, room, a['ply'], a['card']))
                            self.assertEqual({k for k, q in a['behavior_probabilities'].items() if q > 0} - {symbol(x) for x, ok in sure.items() if ok}, set())
                            held = True
                            kept += 1
                            moved += bool(note.get('moved'))
                    if held:
                        self.assertGreaterEqual(result['declarer_tricks'], target, (seed, room))
        finally:
            check.close()
        self.assertGreater(kept, 20)

    def test_the_defender_rule_moves_only_to_the_fewest_hand_overs_within_the_margin(self):
        x8 = dict(claims=dict(cards=0, declarer=False, defender=12, defender_cards=8, contracts='all', guard=True, odds_margin=.25, leaf=0),
                  capture=dict(level=0))
        p = self.make8(x8, gen7=self.GEN8, list_solve=16)
        plain = self.make(Gen7Player, gen7=self.GEN8, list_solve=16)
        tested = moved = 0
        for seed in range(10):
            board = next(generate(1, 900 + seed))
            for room in (0, 1):
                result = self.table(p, board, room)
                for a, o in self.views(board, result):
                    if a['player'] != 'x' or len(o.legal) < 2:
                        continue
                    guard = (a.get('x8') or {}).get('guard')
                    want = plain.choose(o, decision_rng(5, board.id, 'x', o)).card
                    if not guard:
                        self.assertEqual(card(a['card']), want)         # the rule did not act: plain Gen 8's card
                        continue
                    self.assertNotEqual(o.controller % 2, o.contract.declarer % 2)
                    self.assertLessEqual(len(o.known_hands[o.actor]), 8)
                    tested += 1
                    if guard['odds'] is None:
                        continue
                    odds = dict(zip(guard['cards'], guard['odds']))
                    if guard['moved']:
                        moved += 1
                        self.assertEqual(odds[a['card']], min(odds.values()))
                        self.assertGreater(odds[symbol(want)] if symbol(want) in odds else 1., min(odds.values()))
                        u = a['estimates']
                        self.assertLessEqual(abs(u[a['card']]['utility'] - u[symbol(want)]['utility']), .25 + 1e-9)
                    else:
                        self.assertEqual(card(a['card']), want)
        self.assertGreater(tested, 20)
        self.assertGreater(moved, 2)

    def test_an_audited_bot_names_plain_gen8s_card_where_a_feature_changed_it(self):
        class Reference:                                                # a stand-in for the audit reference selector
            def choose(self, o, details, rng):
                return o.legal[0], {}
        x8 = dict(stages=[dict(from_trick=3, to_trick=13, mode='blend', trust=1., layouts=12, cards=3, margin=2.)],
                  claims=dict(cards=8, defender=8, contracts='all', guard=True, leaf=4), capture=dict(level=0, claim_reference='search'))
        p = self.make8(x8, gen7=self.GEN8, list_solve=16)
        p.reference = Reference()
        plain = self.make(Gen7Player, gen7=self.GEN8, list_solve=16)
        plain.reference = Reference()
        named = changed = 0
        for seed in range(4):
            board = next(generate(1, 950 + seed))
            for room in (0, 1):
                for a, o in self.views(board, self.table(p, board, room)):
                    if a['player'] != 'x' or len(o.legal) < 2 or 'estimates' not in a:
                        continue
                    want = plain.choose(o, decision_rng(5, board.id, 'x', o)).card
                    if 'reference_card' in a:
                        named += 1
                        self.assertEqual(card(a['reference_card']), want)
                        self.assertNotEqual(a['reference_card'], a['card'])
                        self.assertEqual(a['prediction_units'], 'x8-against-plain')
                        self.assertTrue(set(a['x8_features']) & {'blend', 'guarantee', 'odds', 'guard'})
                    else:
                        self.assertEqual(card(a['card']), want)
                    changed += card(a['card']) != want
        self.assertGreater(named, 5)
        self.assertEqual(named, changed)

    def test_claims_play_a_card_that_takes_every_trick_and_rollouts_name_gen8s_card(self):
        class Reference:
            def choose(self, o, details, rng):
                return o.legal[0], {}
        x8 = dict(stages=[dict(from_trick=5, to_trick=13, mode='rollout', layouts=12, first=4, seat='draw')],
                  claims=dict(cards=8, full=True, defender=6, leaf=4, contracts='all'), capture=dict(level=0, audit_search=True))
        p = self.make8(x8, gen7=self.GEN8, list_solve=16)
        p.reference = Reference()
        plain = self.make(Gen7Player, gen7=self.GEN8, list_solve=16)
        off = dict(x8, claims=dict(x8['claims'], declarer=False, full=False, defender=0, guard=False))
        unclaimed = self.make8(off, gen7=self.GEN8, list_solve=16)      # the same bot with the decision-level claim logic off
        check = x8_claims.Finder(BIN)
        claims = named = against_bot = 0
        try:
            for seed in range(5):
                board = next(generate(1, 970 + seed))
                for room in (0, 1):
                    for a, o in self.views(board, self.table(p, board, room)):
                        note = a.get('x8')
                        if a['player'] != 'x' or not note:
                            continue
                        if note['mode'] == 'claim':
                            state, sure = check.root(o, need=len(o.known_hands[o.actor]))
                            self.assertEqual(state, 'guaranteed')
                            self.assertTrue(sure[card(a['card'])])
                            claims += 1
                        if 'reference_card' in a:
                            if a['prediction_units'] == 'x8-against-no-claims':     # claims are measured against the bot without them
                                self.assertTrue(set(a['x8_features']) & {'claim', 'guarantee', 'odds', 'guard'})
                                want = unclaimed.choose(o, decision_rng(5, board.id, 'x', o)).card
                                against_bot += 1
                            else:                                                     # rollouts against plain Gen 8's search
                                self.assertEqual(a['prediction_units'], 'x8-against-plain')
                                want = plain.choose(o, decision_rng(5, board.id, 'x', o)).card
                            self.assertEqual(card(a['reference_card']), want)
                            self.assertNotEqual(card(a['reference_card']), card(a['card']))
                            named += 1
        finally:
            check.close()
        self.assertGreater(claims, 5)
        self.assertGreater(named, 5)
        self.assertGreater(against_bot, 2)

    GEN8 = PlayerTests.GEN8



class MixForkTests(Fixture8):
    def test_a_share_of_mixing_only_changes_is_forked_by_position(self):
        """capture.mix_share forks that share of the decisions the mix alone changed, chosen by a hash of the position
        (no random draw): the same position always answers the same, every position at 1 and none at 0."""
        gen8 = PlayerTests.GEN8
        some = self.make8(dict(capture=dict(mix_share=.25)), gen7=gen8)
        every = self.make8({}, gen7=gen8)
        none = self.make8(dict(capture=dict(mix_share=0.)), gen7=gen8)
        picked = []
        for seed in range(40):
            for plies in (1, 9, 17, 25):
                _, o, _ = spot(seed, plies)
                picked.append(some.mix_forked(o))
                self.assertEqual(picked[-1], some.mix_forked(o))
                self.assertTrue(every.mix_forked(o))
                self.assertFalse(none.mix_forked(o))
        self.assertTrue(.12 < np.mean(picked) < .40, np.mean(picked))


class StageClassTests(Fixture8):
    def test_a_games_only_stage_leaves_undoubled_partscores_to_the_search(self):
        from bridge_harness.x8_player import game_or_doubled
        p = self.make8(dict(stages=[dict(from_trick=2, to_trick=13, mode='blend', trust=.25, contracts='games')]), gen7=PlayerTests.GEN8)
        board0, _, _ = __import__('test_gen7').played(3, 0)
        cases = [(Contract(2, 'S', 0), False), (Contract(3, 'N', 0), True), (Contract(4, 'H', 1), True), (Contract(4, 'D', 2), False),
                 (Contract(5, 'C', 3), True), (Contract(1, 'N', 0, 1), True), (Contract(6, 'S', 2), True), (Contract(3, 'S', 1, 2), True)]
        for contract, game in cases:
            self.assertEqual(game_or_doubled(contract), game)
            game_ = Game(Board('t', board0.hands, contract, 0, 'None', ()))
            for _ in range(5):                              # into the second trick
                game_.play(game_.observation().legal[0])
            o = game_.observation()
            self.assertEqual(p.x8_stage(o) is not None, game, str(contract))


if __name__ == '__main__':
    unittest.main()
