import os
import unittest

from bridge_harness import claims
from bridge_harness.core import Board, Contract, Game, card

BIN = os.environ.get('SURE_BIN', '')


def hand(text):
    return tuple(card(x) for x in text.split())


class PositionTest(unittest.TestCase):
    def board(self, declarer):
        # North holds the top spades and hearts; East-West hold the rest. A notrump contract by `declarer`.
        n = hand('SA SK SQ SJ HA HK HQ HJ DA DK DQ DJ CA')
        e = hand('S2 S3 S4 S5 H2 H3 H4 H5 D2 D3 D4 D5 C2')
        s = hand('S6 S7 S8 S9 H6 H7 H8 H9 D6 D7 D8 D9 C3')
        w = hand('ST HT DT CK CQ CJ CT C9 C8 C7 C6 C5 C4')
        hands = (n, e, s, w)
        if declarer % 2:                      # the same deal turned: East-West declare with North's cards in East
            hands = (w, n, e, s)
        return Board('t', hands, Contract(3, 'N', declarer), 0, 'None', ())

    def test_turn_keeps_the_game(self):
        texts = []
        for declarer in (0, 1):
            g = Game(self.board(declarer))
            g.play(g.observation().legal[0])          # the opening lead
            texts.append(claims.position(g.observation()) if g.actor % 2 == declarer % 2 else None)
        self.assertIsNotNone(texts[0])
        self.assertEqual(texts[0], texts[1])

    @unittest.skipUnless(BIN and os.path.exists(BIN), 'SURE_BIN is not set to a built sure_cpp')
    def test_values(self):
        g = Game(self.board(0))
        g.play(card('C2'))                            # East leads; South (dummy) to play, North's ace to come
        o = g.observation()
        state, value = claims.Claims(BIN).verdict(o)
        self.assertEqual(state, 'guaranteed')
        self.assertEqual(max(value.values()), 13)     # thirteen top tricks, the current one included


    def test_first_claim_once_a_hand(self):
        from bridge_harness.plan_player import PlanPlayer
        from bridge_harness.players import Decision
        player = object.__new__(PlanPlayer)        # only the claim log: no net, no search
        player.claim_hand = None
        g = Game(self.board(0))
        g.play(card('C2'))
        firsts = []
        for _ in range(3):                         # three declaring-side decisions of the same hand
            while g.actor % 2:
                g.play(g.observation().legal[0])
            o = g.observation()
            check = dict(state='guaranteed', value={x: 13 - len(o.history) // 4 for x in o.legal}, exact=True, seconds=0.)
            d = player.with_claim(o, Decision(o.legal[0], {}), check)
            firsts.append(d.details['claim']['first'])
            self.assertTrue(d.details['claim']['keeps'])
            g.play(o.legal[0])
        self.assertEqual(firsts, [True, False, False])
        g = Game(self.board(0))                    # the same deal again from the start: a new hand
        g.play(card('C2'))
        o = g.observation()
        d = player.with_claim(o, Decision(o.legal[0], {}), dict(state='guaranteed', value={x: 13 for x in o.legal}, exact=True, seconds=0.))
        self.assertTrue(d.details['claim']['first'])

    @unittest.skipUnless(BIN and os.path.exists(BIN), 'SURE_BIN is not set to a built sure_cpp')
    def test_cheap_question_agrees(self):
        g = Game(self.board(0))
        g.play(card('C2'))
        o = g.observation()
        finder = claims.Claims(BIN)
        full, cheap = finder.verdict(o), finder.verdict(o, exact=False)
        self.assertEqual(full[0], cheap[0])
        need = 9 - o.declarer_tricks
        self.assertEqual({x: int(v >= need) for x, v in full[1].items()}, cheap[1])


if __name__ == '__main__':
    unittest.main()
