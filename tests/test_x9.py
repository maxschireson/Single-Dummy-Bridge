"""X9: the Gen 9 player on the 8X engine (bridge_harness/x9_player.py, Gen 9 task G9-A10)."""
import unittest

from bridge_harness.corpus import generate
from bridge_harness.gen9 import Gen9Player
from bridge_harness.player_model import PlayerModel
from bridge_harness.x8_player import X8Player
from bridge_harness.x9_player import X9Player
from test_x8 import BIN, HAVE_SOLVER, Fixture8


ROLLOUTS = dict(stages=[dict(from_trick=2, to_trick=4, mode='blend', trust=.5, layouts=12, cards=3, margin=2.),
                        dict(from_trick=7, to_trick=13, mode='rollout', layouts=24, first=8, cards=3, prior=.01)])


class X9Tests(Fixture8):
    GEN8 = dict(play_weight=1., early_play_weight=1., early_pool=32, early_min_effective=4.)     # as test_x8.PlayerTests

    def make9(self, x8=None):
        return self.make8(x8, gen7=self.GEN8, cls=X9Player, list_solve=16)

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
        from bridge_harness.core import Game
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


if __name__ == '__main__':
    unittest.main()
