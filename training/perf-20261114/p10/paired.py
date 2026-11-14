#!/usr/bin/env python3
"""Paired differences between nets on the same held-out rows, with standard errors by deal (rows of a deal are
correlated, so the deal is the unit). Input: one or more eval_nets.py --per-deal files over the same data.

    paired.py A=B [C=D ...] --per-deal f1.npz [f2.npz ...]     (A minus B; negative regret = A gives up fewer tricks)
"""
import argparse
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pairs', nargs='+')
    ap.add_argument('--per-deal', nargs='+', required=True)
    a = ap.parse_args()
    z = {}
    for f in a.per_deal:
        with np.load(f) as d:
            z.update({k: d[k] for k in d.files})
    for pr in a.pairs:
        x, y = pr.split('=')
        for m, lab in (('reg', 'regret'), ('nll', 'log-loss')):
            sx, nx, sy, ny = z[f'{x}__{m}_s'], z[f'{x}__{m}_n'], z[f'{y}__{m}_s'], z[f'{y}__{m}_n']
            n = nx + ny
            keep = (nx > 0) & (ny > 0)
            # ratio estimator: per-deal totals, weighted by rows (as the pooled mean weights them)
            w = n[keep] / 2
            dx, dy = sx[keep] / nx[keep], sy[keep] / ny[keep]
            diff = dx - dy
            mean = float((w * diff).sum() / w.sum())
            se = float(np.sqrt(((w * (diff - mean)) ** 2).sum()) / w.sum())
            print(f'{x} - {y}  {lab:8s} {mean:+.5f} +- {se:.5f}  ({keep.sum()} deals)')


if __name__ == '__main__':
    main()
