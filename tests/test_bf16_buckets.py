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


def test_fast_features_equal_generic():
    rng = np.random.default_rng(4)
    for n in (1, 5, 64, 300):
        b = _batch(n, rng)
        b['order'] = rng.integers(0, 53, (n, 52)).astype(np.uint8)
        fast = g._features_np(b)
        g.FAST_FEATURES = False
        try:
            slow = g.features(b)
        finally:
            g.FAST_FEATURES = True
        for x, y in zip(fast, slow):
            assert x.dtype == y.dtype and x.shape == y.shape and np.array_equal(x, y)


def _legal(n, rng):
    legal = np.zeros((n, 52), bool)
    for i in range(n):
        suits = [rng.integers(4)] if rng.random() < .55 else list(rng.choice(4, size=rng.integers(2, 5), replace=False))
        for s in suits:
            legal[i, s * 13 + rng.choice(13, size=int(rng.integers(1, 5)), replace=False)] = True
    return legal


def test_policy_from_legal_suits_only():
    """At the rollout nets' sizes the legal cards' log-probabilities are bit-identical on the machines tested. BLAS
    may pick kernels by matrix size, so other sizes can differ in the last bit (2e-7 seen with tiny layers)."""
    rng = np.random.default_rng(6)
    for dims, exact in ((dict(e=192, t=576, d=384), True), (dict(), False)):
        p = _params(rng, **dims)
        f = g.Bf16Forward(p, torch) if torch is not None else None
        for n in (1, 2, 3, 9, 40, 131, 300):
            b = _batch(n, rng)
            b['legal'] = legal = _legal(n, rng)
            full, part = g.log_softmax(g.forward(p, b)['policy']), g.log_softmax(g.forward_policy(p, b))
            if exact:
                assert np.array_equal(full[legal], part[legal]), n
            assert np.allclose(full[legal], part[legal], rtol=0, atol=1e-5), n
            assert (part[~legal] < -1e8).all()
            if f is not None and exact:
                assert np.array_equal(g.log_softmax(f(b)['policy'])[legal], g.log_softmax(f.policy(b))[legal]), n


if __name__ == '__main__':
    test_policy_from_legal_suits_only()
    test_fast_features_equal_generic()
    test_bucket_sizes()
    test_padded_equals_unpadded()
    print('ok' if torch is not None else 'ok (torch missing: padding test skipped)')
