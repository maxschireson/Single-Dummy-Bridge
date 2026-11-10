"""Function-preserving expansion and portable attention inference checks."""
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','TF_NUM_INTRAOP_THREADS','TF_NUM_INTEROP_THREADS'):
    os.environ[name]='1'
os.environ['TF_CPP_MIN_LOG_LEVEL']='3'
os.environ['TF_ENABLE_ONEDNN_OPTS']='0'
import tempfile
import unittest
from pathlib import Path
import numpy as np
from bridge_harness import policy_v5 as v5
from bridge_harness.auction_policy import export_weights

class PolicyV5Test(unittest.TestCase):
    def test_parent_preservation_and_export(self):
        rng=np.random.default_rng(42)
        x=dict(state=rng.normal(0,.1,(4,737)).astype('float32'),
            actions=rng.integers(0,2,(4,13,171)).astype('float32'),
            calls=rng.integers(0,39,(4,64)).astype('int32'),
            seats=rng.integers(0,5,(4,64)).astype('int32'),
            mask=np.array([[1]*i+[0]*(13-i) for i in (2,5,9,13)],'float32'),
            q=rng.normal(0,1,(4,13)).astype('float32'))
        with tempfile.TemporaryDirectory() as directory:
            parent=Path(directory)/'parent.npz'
            v5.MODE='baseline';base=v5.build_model(737,171);export_weights(base,parent)
            previous=v5.V5Weights(parent).predict(x)
            for mode in ('baseline','wide','attention'):
                with self.subTest(mode=mode):
                    v5.MODE=mode;model=v5.build_model(737,171);v5.restore(model,parent)
                    def prediction():
                        out=model({k:x[k] for k in ('state','actions','calls','seats')})
                        a=out['score'].numpy()[...,0]
                        a-=(a*x['mask']).sum(1,keepdims=True)/x['mask'].sum(1,keepdims=True)
                        return x['q']+out['value'].numpy()+a
                    np.testing.assert_allclose(prediction(),previous,atol=1e-5,rtol=0)
                    if mode=='attention':
                        layer=model.get_layer('att_readout');w=layer.get_weights()
                        w[0]=rng.normal(0,.05,w[0].shape).astype('float32');layer.set_weights(w)
                    path=Path(directory)/(mode+'.npz');v5.export(model,path)
                    np.testing.assert_allclose(v5.V5Weights(path).predict(x),prediction(),atol=1e-5,rtol=0)
                    clone=v5.build_model(737,171);v5.restore(clone,path)
                    np.testing.assert_allclose(clone({k:x[k] for k in ('state','actions','calls','seats')})['score'],
                        model({k:x[k] for k in ('state','actions','calls','seats')})['score'],atol=1e-6)

if __name__=='__main__': unittest.main()
