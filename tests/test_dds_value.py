import unittest,random
import numpy as np
from bridge_harness.dds_value import pack,unpack,encode,corrected_mean
from bridge_harness.core import Board,Contract,Game
from bridge_harness.dds import DDS
from bridge_harness.approx_dds import ApproxDDS

class DDValue(unittest.TestCase):
    def test_random_prefix_correction(self):
        y=np.array([[1.,3.,2.],[2.,4.,3.],[3.,5.,4.],[4.,6.,5.]])
        p=y+np.array([2.,-1.,.5])
        # A constant action-specific model bias is removed even by one audit.
        np.testing.assert_allclose(corrected_mean(p,y[:1]),y.mean(0))
        np.testing.assert_allclose(corrected_mean(np.zeros_like(y),y),y.mean(0))
        with self.assertRaises(ValueError):corrected_mean(p,y[:0])

    def test_roundtrip_symmetries_and_seeded_bounds(self):
        rng=random.Random(854);cards=list(range(52));rng.shuffle(cards)
        g=Game(Board('test',tuple(tuple(cards[i*13:(i+1)*13]) for i in range(4)),Contract(3,'S',0)))
        d=DDS(cache_path='');a=ApproxDDS()
        try:
            for ply in range(16):
                raw=pack(g.hands,0,g.leader,g.trick);hs,trump,lead,tr=unpack(raw)
                self.assertEqual([set(h) for h in hs],g.hands);self.assertEqual(tr,g.trick)
                x,rem,_=encode(raw[None]);self.assertEqual(x.shape,(1,373));self.assertEqual(rem[0],13-ply//4)
                rotated=[hs[(s-1)%4] for s in range(4)];rot=pack(rotated,0,(lead+1)%4,[((s+1)%4,c) for s,c in tr])
                np.testing.assert_array_equal(x,encode(rot[None])[0])
                order=np.array([2,0,3,1]);inv=np.argsort(order);mapping=lambda c:int(13*inv[c//13]+c%13)
                sr=pack([[mapping(c) for c in h] for h in hs],int(inv[trump]),lead,[(s,mapping(c)) for s,c in tr])
                np.testing.assert_array_equal(encode(raw[None],order)[0],encode(sr[None])[0])
                exact,_=d.solve(hs,trump,lead,tr)
                # Exact actor values supplied at the root must survive child parity/reward conversion.
                seeded=a.all_moves(hs,trump,lead,tr,0,guesses=exact)
                for c,z in seeded.items():self.assertEqual(z['estimate'],exact[c])
                noisy={c:float(exact[c])+(-2 if c%2 else 2) for c in exact}
                bounded=a.all_moves(hs,trump,lead,tr,50,guesses=noisy)
                for c,z in bounded.items():
                    self.assertLessEqual(z['lower'],exact[c]);self.assertGreaterEqual(z['upper'],exact[c]);self.assertLessEqual(z['nodes'],50)
                self.assertEqual(a.solve(hs,trump,lead,tr)[0],exact)
                g.play(rng.choice(g.observation().legal))
        finally:d.close();a.close()

if __name__=='__main__':unittest.main()
