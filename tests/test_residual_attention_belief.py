import json,tempfile,unittest
from pathlib import Path
import numpy as np
from bridge_harness.belief_capacity import INPUTS,Weights as DenseWeights
from bridge_harness.residual_attention_belief import build,dropout_generator,export,Weights
from scripts.train_belief_factorial import read

class ResidualAttentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tensorflow as tf
        cls.tf=tf;tf.config.threading.set_intra_op_parallelism_threads(2);tf.config.threading.set_inter_op_parallelism_threads(1)
        tf.config.experimental.enable_op_determinism()
        cls.parent=Path('runs/belief-size-loss-v2-20261110/current_consequence/best.npz')
        ds=json.loads(Path('runs/dense-impact-v5-clean-20261109/dataset.json').read_text())
        cls.samples=[read(next(e for e in ds['shards'] if e['split']=='train' and e['cohort']==c and e['source']==s))
            for c,s in [('historical','bidding'),('historical','ben'),('historical','play'),('recent','play')]]

    def test_nonzero_export_and_parent_preservation(self):
        tf=self.tf;tf.keras.utils.set_random_seed(19);m=build(self.parent,'attention')
        for d in self.samples:
            x={k:d[k][:8] for k in INPUTS}
            np.testing.assert_allclose(m(x,training=False).numpy(),DenseWeights(self.parent).predict(x),atol=2e-6,rtol=1e-6)
        layer=m.get_layer('att_readout');w,b=layer.get_weights();w=np.random.default_rng(8).normal(0,.04,w.shape).astype(np.float32);layer.set_weights([w,b])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'weights.npz';export(m,path,'attention');p=Weights(path)
            for d in self.samples:
                x={k:d[k][:8] for k in INPUTS};np.testing.assert_allclose(p.predict(x),m(x,training=False).numpy(),atol=3e-6,rtol=1e-5)
            with self.assertRaises(KeyError):DenseWeights(path)

    def test_interrupted_updates_match_model_and_optimizer(self):
        tf=self.tf;d=self.samples[-1];x={k:tf.convert_to_tensor(d[k][:8]) for k in INPUTS}
        y=tf.convert_to_tensor(d['owner_target'][:8],tf.int32);mask=tf.convert_to_tensor(d['owner_loss_mask'][:8],tf.float32)
        support=tf.convert_to_tensor(d['support'][:8],tf.bool)
        def create():
            tf.keras.utils.set_random_seed(27);m=build(self.parent,'attention');o=tf.keras.optimizers.AdamW(1e-4);o.build(m.trainable_variables)
            return m,o,tf.train.Checkpoint(model=m,optimizer=o)
        def step(m,o):
            with tf.GradientTape() as tape:
                logits=tf.where(support,m(x,training=True),-1e9)
                loss=tf.reduce_sum(tf.nn.sparse_softmax_cross_entropy_with_logits(labels=y,logits=logits)*mask)/tf.reduce_sum(mask)
            o.apply_gradients(zip(tape.gradient(loss,m.trainable_variables),m.trainable_variables))
        m,o,c=create();dropout_generator(m).state.assign([28,0]);step(m,o)
        with tempfile.TemporaryDirectory() as folder:
            path=c.save(str(Path(folder)/'state'));rng=dropout_generator(m).state.numpy().copy()
            step(m,o);expected=m.get_weights();expected_opt=[v.numpy().copy() for v in o.variables]
            n,p,k=create();k.restore(path).assert_existing_objects_matched();dropout_generator(n).state.assign(rng);step(n,p)
            for a,b in zip(expected,n.get_weights()):np.testing.assert_array_equal(a,b)
            for a,b in zip(expected_opt,p.variables):np.testing.assert_array_equal(a,b.numpy())

if __name__=='__main__':unittest.main()
