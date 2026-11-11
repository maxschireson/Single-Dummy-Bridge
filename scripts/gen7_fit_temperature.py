#!/usr/bin/env python3
"""Fit one temperature for a policy on held-out rows, then write the policy with its logits divided by it.

  python scripts/gen7_fit_temperature.py POLICY.npz DATA.npz VAL_SPLIT OUT.npz

The policy head's last layer is scaled, so the most probable card is unchanged and the probabilities
are recalibrated. Prints log-loss before and after on the fitting rows.
"""
import sys

import numpy as np

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_harness.gen7_net import INPUTS, forward, log_softmax

policy, data, split, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
z = np.load(data)
rows = np.flatnonzero(z['deal_split'][z['deal']] == split)
D = {k: z[k][rows] for k in INPUTS}
chosen = z['meta'][rows][:, 0]
legal = D['legal']
with np.load(policy) as f:
    params = {k: f[k] for k in f.files}
logits = np.concatenate([forward(params, {k: v[i:i + 4096] for k, v in D.items()})['policy'] for i in range(0, len(rows), 4096)])
logits = np.where(legal, logits, -1e9)
r = np.arange(len(rows))


def nll(t):
    return float(-log_softmax(logits / t)[r, chosen].mean())


grid = np.exp(np.linspace(np.log(.5), np.log(3.), 61))
losses = [nll(t) for t in grid]
t = float(grid[int(np.argmin(losses))])
for _ in range(30):                                  # golden-section refinement around the grid's best
    lo, hi = t / 1.05, t * 1.05
    a, b = hi - .618 * (hi - lo), lo + .618 * (hi - lo)
    t = a if nll(a) < nll(b) else b
print(f"rows {len(rows)} | log-loss at T=1 {nll(1.):.4f} | best T {t:.3f} log-loss {nll(t):.4f}")
assert int(params['kind']) == 1, 'suit nets only: the policy is channel 0 of the per-suit decoder'
cols = np.arange(params['wd1'].shape[1]) % 5 == 0
scaled = dict(params)
scaled['wd1'] = params['wd1'].copy(); scaled['wd1'][:, cols] /= t
scaled['bd1'] = params['bd1'].copy(); scaled['bd1'][cols] /= t
np.savez(out, **scaled)
with np.load(out) as f:
    check = {k: f[k] for k in f.files}
again = np.concatenate([forward(check, {k: v[i:i + 4096] for k, v in D.items()})['policy'] for i in range(0, min(len(rows), 8192), 4096)])
ref = logits[:len(again)] / t
print('written', out, '| largest logit difference on 8,192 rows', float(np.abs(np.where(legal[:len(again)], again - ref, 0.)).max()))
