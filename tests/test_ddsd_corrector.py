import random,unittest
import numpy as np
from bridge_harness.core import Board,Contract,Game
from bridge_harness.dds import DDS
from bridge_harness.ddsd_corrector import encode,mask_hidden_features,make_model

class CorrectorTests(unittest.TestCase):
    def setUp(self):
        cards=list(range(52));random.Random(16).shuffle(cards)
        self.board=Board('test',tuple(tuple(sorted(cards[i:i+13])) for i in range(0,52,13)),Contract(3,'N',0))

    def test_dd_score_has_same_horizon_after_action(self):
        solver=DDS(cache_path='');game=Game(self.board);rng=random.Random(8)
        for ply in range(52):
            o=game.observation();c=rng.choice(o.legal)
            if ply>=43:
                before=solver.solve(tuple(tuple(sorted(h)) for h in game.hands),o.contract.trump,o.leader,o.trick)[0][c]
                side=o.actor%2;already=o.declarer_tricks if side==0 else ply//4-o.declarer_tricks
            game.play(c)
            if ply>=43:
                new_already=game.declarer_tricks if side==0 else len(game.history)//4-game.declarer_tricks
                if game.done:after=0
                else:
                    n=game.observation();v=max(solver.solve(tuple(tuple(sorted(h)) for h in game.hands),n.contract.trump,n.leader,n.trick)[0].values())
                    after=v if n.actor%2==side else 13-len(n.history)//4-v
                self.assertEqual(before,new_already-already+after)
        solver.close()

    def test_hidden_hands_are_inputs_but_future_play_is_not(self):
        game=Game(self.board);o=game.observation();hands=[list(h) for h in game.hands];c=o.legal[0]
        x,calls=encode(o,hands,c,7)
        hidden=[s for s,h in enumerate(o.known_hands) if h is None];a,b=hidden[:2]
        hands[a][0],hands[b][0]=hands[b][0],hands[a][0]
        changed,new_calls=encode(o,hands,c,7)
        self.assertFalse(np.array_equal(x,changed));np.testing.assert_array_equal(calls,new_calls)
        self.assertEqual(x.shape,changed.shape)
        np.testing.assert_array_equal(mask_hidden_features(x[None]),mask_hidden_features(changed[None]))

    def test_zero_initialization_preserves_dd(self):
        import torch
        game=Game(self.board);o=game.observation()
        x,calls=encode(o,game.hands,o.legal[0],7)
        model=make_model(len(x));model.eval()
        with torch.no_grad():r=model(torch.tensor(x[None]),torch.tensor(calls[None],dtype=torch.long))
        self.assertEqual(float(r[0]),0.)

if __name__=='__main__':unittest.main()
