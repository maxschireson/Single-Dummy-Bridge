#!/usr/bin/env python3
"""bf16 for the card-play nets: speed on one core, and how far its choices move from fp32, on held-out rows.

  python training/rollout-loop-20261113/bench/bf16.py --rows VAL.npz NET.npz [NET.npz ...]

Run with a Python that has torch (CPU build). NumPy has no bf16 matrix product; torch's CPU kernels (oneDNN) use the
AVX512_BF16 instructions where the CPU has them. Variants of the forward pass (bridge_harness/gen7_net.forward, the
suit-shared net):
  numpy fp32    the production forward (one 2-D product a layer since ecb813a)
  torch fp32    the same in torch: separates torch's own cost from bf16's gain
  torch bf16    every product in bf16 (inputs and weights rounded to bf16, sums in fp32 inside the kernel, outputs bf16)
  torch mixed   bf16 for the encoder, trunk and decoder's first layer; the last layer (wd1: 52 cards x 5 heads) in fp32,
                so the logits themselves are not rounded to bf16
Agreement, against numpy fp32 on the same rows: the first card (argmax) is the same; the mean and largest change of a
legal card's log-probability; the mean total-variation distance between the two card distributions (what a 'draw' seat
in a rollout samples from); and on rows whose cards carry the rollouts' values, the tricks the first card gives up.
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from bridge_harness import gen7_net as G  # noqa: E402

import torch  # noqa: E402

torch.set_num_threads(1)


def load(path):
    with np.load(path) as z:
        return {k: z[k] for k in z.files if k not in G.BANK_KEYS and k != 'bot_vocab'}


def torch_forward(P, batch, mode):
    """gen7_net.forward's suit-shared path in torch. mode: 'fp32', 'bf16' or 'mixed'. Returns the policy logits [n, 52]."""
    lo = torch.float32 if mode == 'fp32' else torch.bfloat16
    cards, g = G.features(batch)
    n = cards.shape[0]
    shown = np.asarray(batch['shown']).astype(np.float32).reshape(n, 4, G.SEAT_SHOWN)[:, :, :G.SUIT_SHOWN * 4]
    about = np.transpose(shown.reshape(n, 4, G.SUIT_SHOWN, 4), (0, 3, 1, 2)).reshape(n, 4, 4 * G.SUIT_SHOWN)
    s = torch.from_numpy(np.ascontiguousarray(np.concatenate([cards.reshape(n, 4, 13 * G.CARD_FEATURES), about], axis=2))).reshape(n * 4, -1).to(lo)
    T = P['_t'][lo]
    s = torch.relu(s @ T['ws0'] + T['bs0'])
    s = torch.relu(s @ T['ws1'] + T['bs1'])                                   # [4n, e]
    e = s.shape[1]
    h = torch.cat([s.reshape(n, 4 * e), torch.from_numpy(np.ascontiguousarray(g)).to(lo)], dim=1) @ T['wt0'] + T['bt0']
    if 'emb_own' in T:
        h = h + T['emb_own'][0] + T['emb_other'][0]                           # bot ids unknown (row 0) in this test
    h = torch.relu(h)
    h = torch.relu(h @ T['wt1'] + T['bt1'])
    t = h.shape[1]
    wd0 = T['wd0']
    d = (s @ wd0[:e]).reshape(n, 4, -1) + (h @ wd0[e:e + t])[:, None, :] + wd0[e + t:e + t + 4][None, :, :] + T['bd0']
    d = torch.relu(d).reshape(n * 4, -1)
    if mode == 'mixed':
        out = d.float() @ P['_t'][torch.float32]['wd1'] + P['_t'][torch.float32]['bd1']
    else:
        out = d @ T['wd1'] + T['bd1']
    policy = out.float().reshape(n, 4, 13, 5)[..., 0].reshape(n, 52).numpy()
    return np.where(batch['legal'], policy, -1e9)


def tensors(P):
    keys = [k for k in ('ws0', 'bs0', 'ws1', 'bs1', 'wt0', 'bt0', 'wt1', 'bt1', 'wd0', 'bd0', 'wd1', 'bd1', 'emb_own', 'emb_other') if k in P]
    P['_t'] = {dt: {k: torch.from_numpy(np.ascontiguousarray(P[k].astype(np.float32))).to(dt) for k in keys}
               for dt in (torch.float32, torch.bfloat16)}
    return P


def log_softmax(x):
    x = x - x.max(axis=1, keepdims=True)
    return x - np.log(np.exp(x).sum(axis=1, keepdims=True))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('nets', nargs='+', type=Path)
    p.add_argument('--rows', type=Path, required=True)
    p.add_argument('--n', type=int, default=24576, help='held-out rows to compare on')
    p.add_argument('--batch', type=int, default=512, help='rows a call in the speed test (a rollout ply is 128 to 512)')
    a = p.parse_args()
    z = np.load(a.rows, allow_pickle=True)
    rng = np.random.default_rng(0)
    pick = np.sort(rng.choice(len(z['deal']), min(a.n, len(z['deal'])), replace=False))
    rows = {k: z[k][pick] for k in G.INPUTS}
    gap, legal = z['gap'][pick].astype(np.float32), z['legal'][pick].astype(bool)
    rated = legal & (gap >= 0)
    has = (z['meta'][pick][:, 10] == 1) & rated.any(1)
    print(f'{len(pick)} held-out rows from {a.rows.name}; {int(has.sum())} with the rollouts\' or search\'s values; torch {torch.__version__}; '
          f'oneDNN bf16 {torch.backends.mkldnn.is_available()}')
    for path in a.nets:
        P = tensors(load(path))
        if int(np.asarray(P['kind'])) == 0:
            print(path, 'is a flat net; skipped'); continue
        ref = np.concatenate([np.asarray(G.forward(P, {k: v[i:i + 4096] for k, v in rows.items()})['policy']) for i in range(0, len(pick), 4096)])
        lp_ref = log_softmax(ref); p_ref = np.exp(lp_ref)
        first_ref = lp_ref.argmax(1)
        b = {k: v[:a.batch] for k, v in rows.items()}

        def clock(f, reps=30):
            f(); s = time.perf_counter()
            for _ in range(reps):
                f()
            return (time.perf_counter() - s) / reps
        t0 = clock(lambda: G.forward(P, b))
        print(f'\n{path.parent.name}/{path.name}  ({a.batch} rows a call, one thread)')
        print(f'  numpy fp32   {a.batch / t0:8.0f} rows/s  1.00x')
        for mode in ('fp32', 'bf16', 'mixed'):
            got = np.concatenate([torch_forward(P, {k: v[i:i + 4096] for k, v in rows.items()}, mode) for i in range(0, len(pick), 4096)])
            lp = log_softmax(got); pr = np.exp(lp)
            dl = np.abs(np.where(legal, lp - lp_ref, 0))
            first = lp.argmax(1)
            tv = .5 * np.abs(pr - p_ref).sum(1)
            reg_ref = gap[np.arange(len(pick)), first_ref][has].mean()
            reg = np.where(rated[np.arange(len(pick)), first], gap[np.arange(len(pick)), first], np.nan)[has]
            t = clock(lambda: torch_forward(P, b, mode))
            print(f'  torch {mode:6s} {a.batch / t:8.0f} rows/s  {t0 / t:4.2f}x | first card same {100 * (first == first_ref).mean():6.2f}% | '
                  f'log-prob change mean {dl.sum() / legal.sum():.4f} max {dl.max():.3f} | TV mean {tv.mean():.4f} | '
                  f'tricks given up {np.nanmean(reg):.4f} (fp32 {reg_ref:.4f})')


if __name__ == '__main__':
    main()
