import unittest,random
from pathlib import Path
from dataclasses import replace
import numpy as np
from bridge_harness.core import Board,Contract,Game
from bridge_harness.belief_plus import encode_observation

def board(seed=7):
    cards=list(range(52));random.Random(seed).shuffle(cards)
    return Board(str(seed),tuple(tuple(sorted(cards[i*13:(i+1)*13])) for i in range(4)),Contract(3,'N',0))

class Features(unittest.TestCase):
    def test_hidden_cards_cannot_change_inputs(self):
        b=board();g=Game(b);o=g.observation();x,s,c=encode_observation(o)
        # Same opening leader's hand, completely different other three hands.
        unknown=[v for seat,h in enumerate(b.hands) if seat!=o.controller for v in h]
        random.Random(8).shuffle(unknown);hands=list(b.hands)
        for i,seat in enumerate(s for s in range(4) if s!=o.controller):hands[seat]=tuple(sorted(unknown[13*i:13*i+13]))
        y,ss,cc=encode_observation(Game(replace(b,hands=tuple(hands))).observation())
        for k in x:np.testing.assert_array_equal(x[k],y[k])
        np.testing.assert_array_equal(c,cc)
        self.assertEqual(set(x),{'state','play','calls','seats','actions'})
    def test_legal_candidates_and_dummy(self):
        g=Game(board());rng=random.Random(2)
        while not g.done:
            o=g.observation();x,s,c=encode_observation(o)
            self.assertEqual(set(c[c>=0]),set(o.legal));self.assertEqual(x['actions'].shape,(13,171))
            for seat,h in enumerate(g.hands):
                for v in h:self.assertTrue(s[v,(seat-o.controller)%4])
            g.play(rng.choice(o.legal))

class Approximate(unittest.TestCase):
    def test_bounds_and_context_after_abort(self):
        from bridge_harness.approx_dds import ApproxDDS
        from bridge_harness.dds import DDS
        a=ApproxDDS();d=DDS(cache_path='');rng=random.Random(33)
        try:
            for seed in range(4):
                g=Game(board(seed))
                while not g.done:
                    o=g.observation()
                    if len(g.history) in (0,1,2,3,13,14,15,25,26,27,37,38,39,45,46,47,49,50,51):
                        exact,_=d.solve(g.hands,o.contract.trump,g.leader,g.trick)
                        for budget in (0,50,100000):
                            approx=a.all_moves(g.hands,o.contract.trump,g.leader,g.trick,budget)
                            self.assertEqual(set(exact),set(approx))
                            for c,z in approx.items():
                                self.assertLessEqual(z['nodes'],budget)
                                self.assertLessEqual(z['lower'],exact[c]);self.assertGreaterEqual(z['upper'],exact[c])
                                if z['exact']:self.assertEqual(z['estimate'],exact[c])
                        # An interrupted search must not poison subsequent exact search.
                        again,_=a.solve(g.hands,o.contract.trump,g.leader,g.trick)
                        self.assertEqual(exact,again)
                    g.play(rng.choice(o.legal))
        finally:a.close();d.close()

if __name__=='__main__':unittest.main()
