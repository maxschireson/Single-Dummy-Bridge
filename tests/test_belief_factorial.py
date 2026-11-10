import unittest
import numpy as np
from scripts.train_belief_factorial import loss_weights
from bridge_harness.belief_capacity import Weights,widen,load,INPUTS
from pathlib import Path
import json

class FactorialTests(unittest.TestCase):
    def test_ordinary_loss_does_not_erase_evaluation_weights(self):
        w=np.array([[1.,2.,4.]],np.float32);d={'card_weight':w.copy()}
        np.testing.assert_array_equal(loss_weights(d,'ordinary'),np.ones_like(w))
        np.testing.assert_array_equal(loss_weights(d,'consequence'),w)
        np.testing.assert_array_equal(d['card_weight'],w)

    def test_double_width_preserves_real_parent_predictions(self):
        parent=Weights('models/belief-v4.npz');expanded=Weights('models/belief-v4.npz')
        expanded.weights=widen(parent.weights,(512,256),seed=2026111001)
        self.assertEqual(sum(x.size for x in expanded.weights),682614)
        ds=json.loads(Path('runs/dense-impact-v5-clean-20261109/dataset.json').read_text())
        for source in ('play','bidding','ben'):
            e=next(e for e in ds['shards'] if e['source']==source and e['split']=='validation')
            d=load(e['file']);x={k:d[k][:32] for k in INPUTS}
            np.testing.assert_allclose(expanded.predict(x),parent.predict(x),atol=1e-6)

if __name__=='__main__':unittest.main()
