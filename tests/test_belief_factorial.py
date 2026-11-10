import unittest
import numpy as np
from scripts.train_belief_factorial import loss_weights
from bridge_harness.belief_capacity import Weights,widen,PLAY_SIZE
from bridge_harness.auction_belief import CALLS,MAX_CALLS

class FactorialTests(unittest.TestCase):
    def test_ordinary_loss_does_not_erase_evaluation_weights(self):
        w=np.array([[1.,2.,4.]],np.float32);d={'card_weight':w.copy()}
        np.testing.assert_array_equal(loss_weights(d,'ordinary'),np.ones_like(w))
        np.testing.assert_array_equal(loss_weights(d,'consequence'),w)
        np.testing.assert_array_equal(d['card_weight'],w)

    def test_double_width_preserves_nonzero_parent_predictions(self):
        rng=np.random.default_rng(17)
        parent=object.__new__(Weights);expanded=object.__new__(Weights)
        shapes=[(len(CALLS)+1,4),(5,2),(64+6*MAX_CALLS+PLAY_SIZE,256),(256,),
                (256,128),(128,),(128,208),(208,)]
        parent.weights=[rng.normal(0,.03,size=s).astype(np.float32) for s in shapes]
        expanded.weights=widen(parent.weights,(512,256),seed=2026111001)
        self.assertEqual(sum(x.size for x in expanded.weights),682614)
        x=dict(state=rng.normal(size=(32,64)).astype(np.float32),play=rng.normal(size=(32,PLAY_SIZE)).astype(np.float32),
               calls=rng.integers(len(CALLS)+1,size=(32,MAX_CALLS)),seats=rng.integers(5,size=(32,MAX_CALLS)))
        np.testing.assert_allclose(expanded.predict(x),parent.predict(x),atol=1e-6)

if __name__=='__main__':unittest.main()
