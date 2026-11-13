import importlib.util
from pathlib import Path
import unittest

import numpy as np

from bridge_harness import gen7_net

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('train_rollout_net', ROOT / 'scripts' / 'train_rollout_net.py')
trainer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trainer)


def batch(n, rng):
    b = dict(state=rng.integers(0, gen7_net.N_STATE, (n, 52)).astype(np.int8), order=rng.integers(0, 53, (n, 52)).astype(np.int8),
             legal=np.zeros((n, 52), bool), ctx=rng.random((n, gen7_net.N_CTX)).astype(np.float32),
             auction=np.zeros((n, gen7_net.N_AUCTION), np.int8), shown=rng.random((n, gen7_net.N_SHOWN)).astype(np.float32))
    b['legal'][:, :13] = True
    return b


class BotVectorTest(unittest.TestCase):
    def test_zero_vectors_change_nothing_and_ids_do(self):
        rng = np.random.default_rng(0)
        plain = trainer.init(1, rng, 64)
        with_bots = dict(plain, emb_own=np.zeros((4, 64), np.float32), emb_other=np.zeros((4, 64), np.float32))
        b = batch(5, rng)
        base = gen7_net.forward(dict(plain, kind=np.array(1)), b)['policy']
        tagged = dict(b, bot_own=np.array([0, 1, 2, 3, 1], np.int32), bot_other=np.array([3, 2, 1, 0, 0], np.int32))
        np.testing.assert_allclose(gen7_net.forward(dict(with_bots, kind=np.array(1)), tagged)['policy'], base, atol=1e-5)
        np.testing.assert_allclose(gen7_net.forward(dict(with_bots, kind=np.array(1)), b)['policy'], base, atol=1e-5)   # ids missing: unknown
        with_bots['emb_own'][1] = rng.standard_normal(64)
        out = gen7_net.forward(dict(with_bots, kind=np.array(1)), tagged)['policy']
        moved = np.abs(out - base)[:, :13].max(axis=1) > 1e-4
        self.assertEqual(moved.tolist(), [False, True, False, False, True])

    def test_array_calls_use_who(self):
        rng = np.random.default_rng(1)
        params = dict(trainer.init(1, rng, 64, bots=3), kind=np.array(1))
        params['emb_own'][2] = rng.standard_normal(64)
        net = object.__new__(gen7_net.PolicyNet)        # weights only: the array entry points need no scorer
        net.params, net.vocab, net.who = params, {'': 0, 'a': 1, 'b': 2}, ('', '')
        b = batch(4, rng)
        unknown = net.log_policy_arrays(b)
        net.who = ('b', 'a')
        told = net.log_policy_arrays(b)
        self.assertGreater(float(np.abs(told - unknown)[:, :13].max()), 1e-4)
        np.testing.assert_allclose(net.policy_and_gap_arrays(b)[0], told, atol=1e-5)

    def test_match_bots_by_name(self):
        meta = np.zeros((3, 11), np.int32)
        meta[:, 8], meta[:, 9] = [1, 2, 0], [2, 1, 1]
        out = trainer.match_bots(meta, ['', 'ben64', 'new-bot'], ['', '6-32', 'ben64'])
        self.assertEqual(out[:, 8].tolist(), [2, 0, 0])
        self.assertEqual(out[:, 9].tolist(), [0, 2, 2])


if __name__ == '__main__':
    unittest.main()
