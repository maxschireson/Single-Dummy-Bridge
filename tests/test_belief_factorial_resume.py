"""Resuming an epoch must preserve gradients, including dropout randomness."""
import tempfile,unittest
from pathlib import Path
import numpy as np
import tensorflow as tf
from scripts.train_belief_factorial import reset_dropout

class EpochResumeTest(unittest.TestCase):
    def test_resumed_update_matches_uninterrupted(self):
        tf.keras.utils.set_random_seed(91)
        def build():
            model=tf.keras.Sequential([tf.keras.Input((8,)),tf.keras.layers.Dense(16,activation='relu'),
                tf.keras.layers.Dropout(.15),tf.keras.layers.Dense(4)])
            opt=tf.keras.optimizers.AdamW(.0001);opt.build(model.trainable_variables)
            return model,opt,tf.train.Checkpoint(model=model,optimizer=opt)
        model,opt,checkpoint=build();x=tf.ones((32,8));y=tf.range(32)%4
        def epoch(m,o,number):
            reset_dropout(m,2026111001+number)
            for _ in range(3):
                with tf.GradientTape() as t:
                    loss=tf.reduce_mean(tf.nn.sparse_softmax_cross_entropy_with_logits(labels=y,logits=m(x,training=True)))
                o.apply_gradients(zip(t.gradient(loss,m.trainable_variables),m.trainable_variables))
        epoch(model,opt,1)
        with tempfile.TemporaryDirectory() as tmp:
            path=checkpoint.save(str(Path(tmp)/'ckpt'))
            epoch(model,opt,2)
            resumed,other_opt,other_ckpt=build();other_ckpt.restore(path).assert_existing_objects_matched()
            epoch(resumed,other_opt,2)
            for a,b in zip(model.get_weights(),resumed.get_weights()):np.testing.assert_array_equal(a,b)
            for a,b in zip(opt.variables,other_opt.variables):np.testing.assert_array_equal(a.numpy(),b.numpy())

if __name__=='__main__':unittest.main()
