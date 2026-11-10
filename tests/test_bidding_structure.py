import unittest
import tempfile
import numpy as np
from bridge_harness.bidding_env import BidObservation, encode, legal_mask, masked_probabilities
from bridge_harness.bidding_structure import features, make_adapter, VARIANTS, Trainer


class StructureTests(unittest.TestCase):
    @staticmethod
    def observations():
        hand = (0, 1, 5, 9, 10, 13, 14, 25, 26, 27, 38, 39, 51)
        # Exchange low ranks without changing compressed hand, shape, or HCP.
        other = (0, 2, 5, 9, 10, 13, 14, 25, 26, 27, 38, 39, 51)
        return [BidObservation(h,0,0,'None',()) for h in (hand,other)]

    def test_exact_rank_information(self):
        obs = self.observations()
        np.testing.assert_array_equal(encode(obs[0]),encode(obs[1]))
        f = features(obs)
        self.assertFalse(np.array_equal(f['hand'][0],f['hand'][1]))
        self.assertEqual(f['hand'].sum(),26)

    def test_public_call_order_and_roles(self):
        hand = self.observations()[0].hand
        obs = BidObservation(hand,1,0,'NS',('1C','PASS','1H','PASS','2H'))
        f = features([obs])
        np.testing.assert_array_equal(f['roles'][0,:6],[4,3,0,1,2,3])
        self.assertEqual(int((f['calls']!=0).sum()),6)

    def test_zero_residual_and_policy_gradient(self):
        import tensorflow as tf
        obs = self.observations(); f = features(obs)
        rng = np.random.default_rng(3)
        base = rng.uniform(.01,1,(2,40)).astype(np.float32); base /= base.sum(axis=1,keepdims=True)
        f.update(hidden=rng.normal(size=(2,256)).astype(np.float32),base=base)
        for variant in VARIANTS:
            with self.subTest(variant=variant):
                tf.keras.utils.set_random_seed(19)
                model = make_adapter(variant)
                p,v = model(f)
                np.testing.assert_allclose(p.numpy(),base,rtol=1e-5,atol=1e-7)
                np.testing.assert_array_equal(v.numpy(),[0,0])
                self.assertLess(model.count_params(),70000)
                masks = np.array([legal_mask(o.dealer,o.calls) for o in obs])
                pp = np.array([masked_probabilities(x,m,.005) for x,m in zip(base,masks)])
                actions = np.array([2,2],np.int32)
                arrays = dict(f,masks=masks,actions=actions,old_logp=np.log(pp[:,2]),old_value=np.zeros(2,np.float32))
                trainer = Trainer(model)
                metrics = trainer.train(arrays,[10,-10],rng,epochs=1,minibatch=2)
                self.assertEqual(metrics['minibatches'],1)
                self.assertLess(abs(metrics['last']['approx_kl']),1e-6)
                self.assertTrue(np.any(np.abs(model.delta.kernel.numpy())>0))
                expected = model(f)[0].numpy()
                with tempfile.TemporaryDirectory() as directory:
                    checkpoint = trainer.checkpoint.save(directory+'/ckpt')
                    restored = make_adapter(variant)
                    other_trainer = Trainer(restored)
                    other_trainer.checkpoint.restore(checkpoint).assert_consumed()
                    np.testing.assert_allclose(restored(f)[0].numpy(),expected,rtol=1e-6,atol=1e-7)


if __name__=='__main__':
    unittest.main()
