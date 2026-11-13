"""The suit net's forward pass against the plain layer-by-layer form it was rewritten from (dense 2-D products and a
split decoder layer): same outputs, every head."""
import tempfile
import unittest
from pathlib import Path

import numpy as np

from bridge_harness import gen7_net as G
from bridge_harness.gen7_net import encode, stack
from test_gen7 import net_weights, played


def reference(params, batch):
    """The suit net (kind 1) written with a 3-D matmul per layer and the decoder input concatenated."""
    cards, g = G.features(batch)
    n = cards.shape[0]
    shown = batch['shown'].astype(np.float32).reshape(n, 4, G.SEAT_SHOWN)[:, :, :G.SUIT_SHOWN * 4]
    about_suit = np.transpose(shown.reshape(n, 4, G.SUIT_SHOWN, 4), (0, 3, 1, 2)).reshape(n, 4, 4 * G.SUIT_SHOWN)
    s = np.concatenate([cards.reshape(n, 4, 13 * G.CARD_FEATURES), about_suit], axis=2)
    s = np.maximum(s @ params['ws0'] + params['bs0'], 0)
    s = np.maximum(s @ params['ws1'] + params['bs1'], 0)
    h = np.concatenate([s.reshape(n, -1), g], axis=1)
    h = np.maximum(h @ params['wt0'] + params['bt0'], 0)
    h = np.maximum(h @ params['wt1'] + params['bt1'], 0)
    slot = np.broadcast_to(np.eye(4, dtype=np.float32)[None], (n, 4, 4))
    d = np.concatenate([s, np.broadcast_to(h[:, None, :], (n, 4, h.shape[1])), slot], axis=2)
    d = np.maximum(d @ params['wd0'] + params['bd0'], 0)
    out = (d @ params['wd1'] + params['bd1']).reshape(n, 4, 13, 5)
    policy = np.where(batch['legal'], out[..., 0].reshape(n, 52), -1e9)
    return dict(policy=policy, gap=out[..., 1].reshape(n, 52), owner=out[..., 2:].reshape(n, 52, 3),
                tricks=(h @ params['wk'] + params['bk'])[:, 0])


class ForwardTests(unittest.TestCase):
    def test_the_rewritten_suit_net_matches_the_plain_form(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'net.npz'
            net_weights(path, seed=3, width=96)
            params = dict(np.load(path))
        rows = [encode(played(seed, plies)[1].observation()) for seed in range(4) for plies in (0, 9, 25, 40)]
        batch = stack(rows)
        got, want = G.forward(params, batch), reference(params, batch)
        for key in ('policy', 'gap', 'owner', 'tricks'):
            np.testing.assert_allclose(got[key], want[key], rtol=1e-5, atol=1e-5, err_msg=key)


if __name__ == '__main__':
    unittest.main()
