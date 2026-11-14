"""bf16 forward passes padded to fixed batch sizes give the same outputs as unpadded ones (gen7_net.bucket).

Skipped without torch. Run: python3 tests/test_bf16_buckets.py   (or under pytest)
"""
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness import gen7_net as g  # noqa: E402

try:
    import torch
except ImportError:          # pragma: no cover
    torch = None


def _params(rng, e=48, t=64, d=40, vocab=4):
    k_suit = 13 * g.CARD_FEATURES + 4 * g.SUIT_SHOWN
    shapes = dict(ws0=(k_suit, e), bs0=(e,), ws1=(e, e), bs1=(e,), wt0=(4 * e + g.N_GLOBAL, t), bt0=(t,),
                  wt1=(t, t), bt1=(t,), wd0=(e + t + 4, d), bd0=(d,), wd1=(d, 65), bd1=(65,), wk=(t, 1), bk=(1,),
                  emb_own=(vocab, t), emb_other=(vocab, t))
    p = {k: (rng.standard_normal(s) / np.sqrt(s[0])).astype(np.float32) for k, s in shapes.items()}
    p['kind'] = np.array(1)
    return p


def _batch(n, rng):
    return dict(state=rng.integers(0, 11, (n, 52)).astype(np.uint8), order=rng.integers(0, 52, (n, 52)).astype(np.uint8),
                legal=rng.random((n, 52)) < .2, ctx=rng.random((n, g.N_CTX)).astype(np.float32),
                auction=(rng.random((n, g.N_AUCTION)) < .05).astype(np.uint8),
                shown=rng.random((n, g.N_SHOWN)).astype(np.float32),
                bot_own=rng.integers(0, 4, n).astype(np.int32), bot_other=rng.integers(0, 4, n).astype(np.int32))


def test_bucket_sizes():
    assert [g.bucket(n) for n in (1, 2, 3, 5, 33, 129, 513, 1025, 1300)] == [1, 2, 4, 8, 48, 160, 640, 1280, 1536]
    for n in range(1, 3000):
        assert n <= g.bucket(n) <= max(2 * n, n + 256)


def test_padded_equals_unpadded():
    if torch is None:
        return
    rng = np.random.default_rng(3)
    f = g.Bf16Forward(_params(rng), torch)
    for n in (1, 3, 7, 13, 33, 57, 99, 130, 301, 513):
        b = _batch(n, rng)
        plain, padded = f._call(b), f(b)
        for k in ('policy', 'gap', 'owner', 'tricks'):
            assert padded[k].shape == plain[k].shape
            assert np.array_equal(padded[k], plain[k]), (n, k, float(np.abs(padded[k] - plain[k]).max()))


if __name__ == '__main__':
    test_bucket_sizes()
    test_padded_equals_unpadded()
    print('ok' if torch is not None else 'ok (torch missing: padding test skipped)')
