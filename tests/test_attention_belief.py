import unittest
from dataclasses import replace
import numpy as np
from bridge_harness.core import Board, Contract, Game
from bridge_harness.attention_belief import encode, make_model, per_position_loss
from bridge_harness.belief_consequence import public_key, importance


def board():
    deck = np.random.default_rng(51).permutation(52)
    return Board('test', tuple(tuple(sorted(map(int,deck[s*13:(s+1)*13]))) for s in range(4)),
                 Contract(3,'N',0))


class AttentionBeliefTests(unittest.TestCase):
    def test_hidden_deal_not_an_input(self):
        b=board();g=Game(b);o=g.observation()
        h=[list(x) for x in b.hands]
        hidden=[s for s,x in enumerate(o.known_hands) if x is None]
        a,c=hidden[:2];h[a][0],h[c][0]=h[c][0],h[a][0]
        other=Game(replace(b,hands=tuple(tuple(sorted(x)) for x in h))).observation()
        self.assertEqual(public_key(o),public_key(other))
        x,_=encode(o);y,_=encode(other)
        for k in x:np.testing.assert_array_equal(x[k],y[k])

    def test_support_masks_actual_owners(self):
        g=Game(board())
        while not g.done:
            o=g.observation();x,_=encode(o);s=x['support'];m=s.sum(-1)>1
            for seat,hand in enumerate(g.hands):
                for c in hand:self.assertTrue(s[c,(seat-o.controller)%4])
            for _,c in o.history:self.assertFalse(s[c].any())
            for seat,hand in enumerate(o.known_hands):
                if hand is not None:self.assertFalse(m[list(hand)].any())
            g.play(o.legal[0])

    def test_weight_detects_decision_reversal_not_common_uncertainty(self):
        o=Game(board()).observation()
        class Belief:
            def logits(self,o):return np.zeros((52,4))
        class Solver:
            def __init__(self,reverse):self.reverse=reverse
            def solve_batch(self,worlds,*args,**kwargs):
                vals=[]
                for i in range(len(worlds)):
                    # Defender to 3NT: 5 versus 3 future tricks crosses the contract boundary.
                    v={c:3 for c in o.legal}
                    v[o.legal[0]]=5 if i<16 or not self.reverse else 3
                    v[o.legal[1]]=5 if i>=16 and self.reverse else 3
                    vals.append((v,0))
                return vals
        fixed=importance(o,Belief(),Solver(False))
        reversal=importance(o,Belief(),Solver(True))
        self.assertEqual(fixed['weight'],1)
        self.assertGreater(reversal['weight'],1)
        self.assertLessEqual(reversal['weight'],4)

    def test_masked_loss_and_checkpoint(self):
        import io,torch
        torch.set_num_threads(1);torch.manual_seed(42)
        x,_=encode(Game(board()).observation())
        x={k:torch.from_numpy(v[None]) for k,v in x.items()}
        m=make_model();m.eval();z=m(x)
        target=x['support'].long().argmax(-1);mask=x['support'].sum(-1)>1
        loss=per_position_loss(z,target,x['support'],mask)
        loss.sum().backward()
        self.assertTrue(all(torch.isfinite(p.grad).all() for p in m.parameters() if p.grad is not None))
        changed=z.detach().clone();changed[~x['support']]=1e6
        torch.testing.assert_close(loss,per_position_loss(changed,target,x['support'],mask))
        buf=io.BytesIO();torch.save(m.state_dict(),buf);buf.seek(0)
        n=make_model();n.load_state_dict(torch.load(buf,weights_only=True));n.eval()
        torch.testing.assert_close(z,n(x),atol=0,rtol=0)


if __name__=='__main__':unittest.main()
