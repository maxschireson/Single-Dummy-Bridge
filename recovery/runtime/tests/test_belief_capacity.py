import unittest
import tempfile
from pathlib import Path
from dataclasses import replace
import numpy as np
from bridge_harness.auction_belief import encode_auction
from bridge_harness.belief_capacity import PLAY_SIZE,encode_play,widen,Weights,make_model
from bridge_harness.core import Board,Game,Contract


class CapacityTests(unittest.TestCase):
    def board(self):
        hands=tuple(tuple(range(i,52,4)) for i in range(4))
        return Board('test',hands,Contract(1,'N',0),0,'None',('1N','PASS','PASS','PASS'),'test')

    def test_observation_boundary_and_history(self):
        g=Game(self.board());o=g.observation();x,s=encode_play(o)
        self.assertEqual(x['play'].shape,(PLAY_SIZE,))
        # Alter only two unobserved hands; opening-lead observer is East.
        b=self.board();h=list(b.hands);h[0],h[2]=h[2],h[0]
        other=Game(replace(b,hands=tuple(h))).observation()
        xx,ss=encode_play(other)
        for k in x:np.testing.assert_array_equal(x[k],xx[k])
        np.testing.assert_array_equal(s,ss)
        g.play(o.legal[0]);after,sup=encode_play(g.observation())
        self.assertFalse(np.array_equal(x['play'],after['play']))
        self.assertFalse(sup[o.legal[0]].any())

    def test_widen_preserves_function_and_numpy_export(self):
        import tensorflow as tf
        from bridge_harness.auction_belief import make_model as old_model
        tf.keras.utils.set_random_seed(4)
        old=old_model(64)
        # Nonzero trained-like output to avoid a vacuous zero-logit test.
        weights=old.get_weights();weights[-2]=np.random.default_rng(8).normal(0,.02,weights[-2].shape).astype('float32');old.set_weights(weights)
        x,_=encode_play(Game(self.board()).observation());x={k:v[None] for k,v in x.items()}
        oldx={k:v for k,v in x.items() if k!='play'}
        for size in ((64,64),(256,128)):
            model=make_model(size);model.set_weights(widen(weights,size))
            np.testing.assert_allclose(model(x).numpy(),old(oldx).numpy(),atol=1e-6)
            with tempfile.TemporaryDirectory() as d:
                p=Path(d)/'w.npz';np.savez(p,**{f'w{i}':w for i,w in enumerate(model.get_weights())})
                np.testing.assert_allclose(Weights(p).predict(x),model(x).numpy(),atol=1e-6)

    def test_relative_play_rotation(self):
        b=self.board();g=Game(b)
        for _ in range(7):g.play(g.observation().legal[0])
        h=b.hands[-1:]+b.hands[:-1]
        rotated=replace(b,hands=h,dealer=1,contract=replace(b.contract,declarer=1))
        other=Game(rotated)
        for _,c in g.history:other.play(c)
        x,s=encode_play(g.observation());xx,ss=encode_play(other.observation())
        for k in x:np.testing.assert_array_equal(x[k],xx[k])
        np.testing.assert_array_equal(s,ss)

if __name__=='__main__':unittest.main()
