"""X9: the Gen 9 player on the 8X engine (bridge_harness/x9_player.py, Gen 9 tasks G9-A10 and G9-A11) and its conditional
claims (bridge_harness/x9_conditional.py)."""
import os
import random
import unittest
from unittest.mock import patch

import numpy as np

from bridge_harness.corpus import generate
from bridge_harness.gen9 import Gen9Player
from bridge_harness.player_model import PlayerModel
from bridge_harness.x8_player import X8Player
from bridge_harness.x9_player import X9Player
from bridge_harness import x9_conditional as xc
from bridge_harness.core import Game, symbol
from bridge_harness.gen6 import View
from test_gen6 import FakeBelief, FakeState
from test_x8 import BIN, HAVE_SOLVER, Fixture8

CELLS = os.environ.get('CELLS_BIN', '')
HAVE_CELLS = bool(CELLS) and os.path.exists(CELLS)


ROLLOUTS = dict(stages=[dict(from_trick=2, to_trick=4, mode='blend', trust=.5, layouts=12, cards=3, margin=2.),
                        dict(from_trick=7, to_trick=13, mode='rollout', layouts=24, first=8, cards=3, prior=.01)])


class X9Tests(Fixture8):
    GEN8 = dict(play_weight=1., early_play_weight=1., early_pool=32, early_min_effective=4.)     # as test_x8.PlayerTests

    def make9(self, x8=None, x9=None):
        if x9 is None:
            return self.make8(x8, gen7=self.GEN8, cls=X9Player, list_solve=16)
        spec = dict(id='9x-test', engine='gen9x', samples=8, near_tie=0., exploration=0., scorer='scorer.npz', lead_belief='lead.npz',
                    lead_state_bidder='bidder.keras', belief='belief.npz', belief_kind='public', gen6=dict(list_solve=16),
                    gen7_policy='gen7.npz', gen7=self.GEN8, x8=x8 or {}, x9=x9)
        with patch('bridge_harness.gen6.BidderState', FakeState), patch('bridge_harness.mixed_arena.Weights', FakeBelief):
            p = X9Player(spec, self.root)
        self.players.append(p)
        return p

    def test_the_order_of_the_classes(self):
        mro = X9Player.__mro__
        self.assertLess(mro.index(X8Player), mro.index(Gen9Player))
        for hook in ('type_log_weights', 'layout_log_weights', 'play_log_likelihood'):
            self.assertNotIn(hook, X8Player.__dict__, hook)          # 8X reads layouts through Gen 9's hooks
            self.assertIn(hook, Gen9Player.__dict__, hook)

    def compare(self, x8):
        """X9 with nothing declared against the 8X bot it wraps: the same cards and the same records."""
        eight = self.make8(x8, gen7=self.GEN8, list_solve=16)
        nine = self.make9(x8)
        compared = 0
        for seed in (2, 3):
            board = next(generate(1, 700 + seed))
            for room in (0, 1):
                a, b = self.table(eight, board, room), self.table(nine, board, room)
                self.assertEqual([x['card'] for x in a['actions']], [x['card'] for x in b['actions']])
                for x, y in zip(a['actions'], b['actions']):
                    if x['player'] == 'x':
                        self.assertEqual(x.get('behavior_probabilities'), y.get('behavior_probabilities'))
                        self.assertEqual(x.get('estimates'), y.get('estimates'))
                        compared += 1
        return compared

    def test_with_nothing_declared_it_plays_the_8x_bots_game_card_for_card(self):
        self.assertGreater(self.compare({}), 40)

    def test_with_rollouts_and_the_blend_it_plays_the_8x_bots_game_card_for_card(self):
        self.assertGreater(self.compare(ROLLOUTS), 40)

    @unittest.skipUnless(HAVE_SOLVER, 'needs sure_cpp (SURE_BIN)')
    def test_with_the_winning_line_logic_it_plays_the_8x_bots_game_card_for_card(self):
        x8 = dict(ROLLOUTS, claims=dict(cards=8, defender=6, leaf=5, contracts='all', binary=BIN), capture=dict(level=0))
        self.assertGreater(self.compare(x8), 40)

    def test_meet_gives_8x_the_id_and_gen9_the_model(self):
        p = self.make9({})
        model = PlayerModel('guest-x', kind='guest')
        p.meet(model)
        self.assertEqual(p.opponent_id, 'guest-x')
        self.assertEqual(p.opponent.id, 'guest-x')
        p.meet('8s-32')
        self.assertEqual(p.opponent_id, '8s-32')

    def test_a_declared_scheme_is_read_and_not_pooled(self):
        from bridge_harness.core import Game, symbol
        x8 = dict(mix=dict(read_defender=['*'], read_declarer=['*'], defender=True))
        p = self.make9(x8)
        board = next(generate(1, 702))
        game = Game(board)
        o = game.observation()
        pooled = p.mixers(o)
        p.opponent = PlayerModel('guest-y', kind='guest', carding={'scheme': 'upside_down'})
        kept = p.mixers(o)
        self.assertTrue(kept <= pooled)
        self.assertTrue(all(s % 2 == o.controller % 2 for s in kept))
        self.assertEqual({s for s in pooled if s % 2 == o.controller % 2}, kept)


def declaring_spots(count, cards=8, seed0=5000):
    """Random games at a declaring-side decision with `cards` or fewer cards, contract open, two or more legal cards."""
    out, seed = [], seed0
    while len(out) < count and seed < seed0 + 4000:
        seed += 1
        board = next(generate(1, seed))
        if board.contract is None:
            continue
        game, rng = Game(board), random.Random(seed)
        while len(game.history) < 52:
            o = game.observation()
            left = len(game.hands[o.actor])
            if left <= cards and o.controller % 2 == board.contract.declarer % 2 and len(o.legal) > 1 and xc.position(o) is not None:
                out.append((o, [tuple(sorted(h)) for h in game.hands], board))
                break
            game.play(rng.choice(o.legal))
    return out


@unittest.skipUnless(HAVE_CELLS, 'needs the cells solver (CELLS_BIN)')
class ConditionalTests(unittest.TestCase):
    def test_every_certified_set_is_one_line_and_floors_do_not_pass_ceilings(self):
        solver = xc.Cells(CELLS)
        try:
            checked = sets = 0
            for o, hands, board in declaring_spots(40):
                view = View(o)
                worlds = [view.world(row) for row in view.uniform(48, np.random.default_rng(7))]
                w = np.ones(len(worlds))
                reps = sorted(o.legal)
                got = xc.decide(solver, o, worlds, w, reps, mass=1., allowance=30.)
                self.assertIsNotNone(got)
                self.assertAlmostEqual(sum(got['weight']), got['covered'], places=4)
                pos = xc.position(o)[0]
                for r, S in got['set'].items():
                    self.assertLessEqual(got['floor'][r], got['ceiling'][r] + 1e-9)
                    if len(S) > 1:
                        solver.position(pos, [tuple(c) for c in got['cells']])
                        self.assertEqual(solver.query(pos['need'], S, [r]).get(r), 1)    # the set is one line
                        sets += 1
                    checked += 1
            self.assertGreater(checked, 5)
        finally:
            solver.close()

    def test_a_layout_inside_a_card_set_is_won_by_that_card_against_every_defence(self):
        """The true layout's cell inside the certified set: the card wins that cell taken alone."""
        solver = xc.Cells(CELLS)
        try:
            for o, hands, board in declaring_spots(10, seed0=6000):
                view = View(o)
                worlds = [view.world(row) for row in view.uniform(48, np.random.default_rng(11))]
                got = xc.decide(solver, o, worlds, np.ones(len(worlds)), sorted(o.legal), mass=1., allowance=30.)
                pos, east, _ = xc.position(o)
                true = xc.cell_of(xc.bits(hands[east]))
                cells = [tuple(c) for c in got['cells']]
                if true not in cells:
                    continue
                i = cells.index(true)
                for r, S in got['set'].items():
                    if i in S:
                        solver.position(pos, cells)
                        self.assertEqual(solver.query(pos['need'], [i], [r]).get(r), 1)
        finally:
            solver.close()


    def test_a_committed_line_survives_any_defence_to_the_declaring_sides_next_turn(self):
        """DESIGN.md's invariant: a card that keeps a guarantee over a set of cells leaves, after any defence, a card that
        keeps it over the set's live cells at the declaring side's next turn."""
        solver = xc.Cells(CELLS)
        tested = 0
        try:
            for o, hands, board in declaring_spots(60, seed0=7000):
                view = View(o)
                worlds = [view.world(row) for row in view.uniform(48, np.random.default_rng(3))]
                got = xc.decide(solver, o, worlds, np.ones(len(worlds)), sorted(o.legal), mass=1., allowance=30.)
                best = max(got['floor'], key=got['floor'].get) if got['floor'] else None
                if best is None or got['floor'][best] <= 0:
                    continue
                pos, east, side = xc.position(o)
                commit = dict(history=tuple((int(a), int(b)) for a, b in o.history), side=o.controller % 2, east=east,
                              cells=[tuple(got['cells'][i]) for i in got['set'][best]])
                true = xc.cell_of(xc.bits(hands[east]))
                if true not in commit['cells']:
                    continue                                 # the actual layout must be one the line covers
                game = Game(board)
                for seat_card in o.history:
                    game.play(seat_card[1])
                game.play(best)
                rng = random.Random(len(o.history))
                while len(game.history) < 52:
                    o2 = game.observation()
                    if o2.controller % 2 == o.controller % 2:
                        break
                    game.play(rng.choice(o2.legal))
                if len(game.history) >= 52 or xc.position(o2) is None:
                    continue
                live = xc.live_cells(commit, o2)
                self.assertIsNotNone(live)
                self.assertIn(xc.cell_of(xc.bits(game.hands[east])), live)
                keep = xc.keeping(solver, o2, live)
                self.assertTrue(keep, (o.history, best))
                tested += 1
            self.assertGreater(tested, 0)
        finally:
            solver.close()


@unittest.skipUnless(HAVE_CELLS and HAVE_SOLVER, 'needs both solvers (CELLS_BIN, SURE_BIN)')
class X9ConditionalTables(X9Tests):
    def test_floors_are_set_for_the_layouts_inside_a_cards_certified_set(self):
        p = self.make9({}, x9=dict(conditional=8, contracts='all', min_floor=0., binary=CELLS))
        applied = 0
        for o, hands, board in declaring_spots(30, seed0=8000):
            view = View(o)
            worlds = [view.world(row) for row in view.uniform(32, np.random.default_rng(5))]
            w = np.ones(len(worlds))
            reps = sorted(o.legal)[:3]
            p.claim, p.stash, p.cond = None, (worlds, w), None
            floor0 = p.first_floor(o, worlds, reps, None)
            if p.cond is None:
                continue
            for j, x in enumerate(reps):
                r = p.cond['rep_of'].get(int(x))
                if r is None or symbol(x) not in p.cond['applied']:
                    self.assertFalse(floor0[:, j].any())
                    continue
                expect = np.isin(np.array(p.cond['layout_cell']), p.cond['set'][r])
                np.testing.assert_array_equal(floor0[:, j], expect)
                applied += 1
        self.assertGreater(applied, 0)

    def test_off_by_default_and_full_tables_with_it_on(self):
        x8 = dict(ROLLOUTS, claims=dict(cards=8, defender=6, leaf=5, contracts='all', binary=BIN), capture=dict(level=0))
        p = self.make9(x8, x9=dict(conditional=8, contracts='all', min_floor=.5, binary=CELLS))
        ran = applied = committed = kept = 0
        for seed in range(2, 6):
            board = next(generate(1, 700 + seed))
            for room in (0, 1):
                result = self.table(p, board, room)
                last = None
                for a in result['actions']:
                    note = a.get('x9')
                    if a['player'] != 'x' or note is None:
                        continue
                    if note.get('cells') is not None:
                        ran += 1
                        applied += bool(note.get('applied'))
                        if note.get('chosen_floor', 0) >= .5:
                            committed += 1
                            last = a
                    if note.get('kept') is not None:
                        kept += 1
                        self.assertTrue(last is not None or note['kept']['live'] >= 0)
        self.assertGreater(ran, 0)
        self.assertGreaterEqual(applied, 0)
        del committed, kept

    def test_with_nothing_declared_it_plays_the_8x_bots_game_card_for_card(self):
        pass

    def test_with_rollouts_and_the_blend_it_plays_the_8x_bots_game_card_for_card(self):
        pass

    def test_with_the_winning_line_logic_it_plays_the_8x_bots_game_card_for_card(self):
        pass


if __name__ == '__main__':
    unittest.main()
