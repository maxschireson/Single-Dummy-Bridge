"""Score hand-fit scorers on validation sets: loss and accuracy by kind of hand.

  AUCTION_BELIEF=path/to/analysis/auction_belief python eval_scorer.py SCORER.npz [SCORER.npz ...] -- VAL.npz [VAL.npz ...]
"""
import os
import sys

import numpy as np
sys.path.insert(0, os.environ.get('AUCTION_BELIEF', 'analysis/auction_belief'))   # research/joint-auction-belief-20261110's analysis/auction_belief, patched
from fit import batch, load, logits  # noqa: E402

a = sys.argv[1:]
cut = a.index('--')
scorers, vals = a[:cut], a[cut + 1:]
for vp in vals:
    d = load([vp])
    n = len(d['label'])
    for sp in scorers:
        p = dict(np.load(sp))
        zs = []
        for s in range(0, n, 8000):
            xh, xa, _ = batch(d, np.arange(s, min(s + 8000, n)))
            zs.append(np.asarray(logits(p, xh, xa)))
        z = np.concatenate(zs).astype(np.float64)
        y = d['label'].astype(np.float64)
        k = d['kind']
        l = np.logaddexp(0, z) - y * z
        acc = lambda m: np.mean((z[m] > 0) == (y[m] > .5))
        bk = lambda m: l[m].mean()
        print(f"{vp.split('/')[-1]:22s} {sp.split('/')[-1]:22s} rows {n} | loss {l.mean():.4f} (true {bk(k == 0):.4f}, random {bk(k == 1):.4f}, near {bk(k == 2):.4f})"
              f" | acc true {acc(k == 0):.3f} random {acc(k == 1):.3f} near {acc(k == 2):.3f} | mean P(fit) true {np.mean(1 / (1 + np.exp(-z[k == 0]))):.3f}"
              f" | fit share random {y[k == 1].mean():.3f} near {y[k == 2].mean():.3f}", flush=True)
