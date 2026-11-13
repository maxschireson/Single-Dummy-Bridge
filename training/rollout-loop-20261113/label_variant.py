#!/usr/bin/env python3
"""A variant of a row set built with scripts/gen7_build_dataset.py --rollout-layouts, for the label-quality and
tables-against-positions experiments (PLAN.md):

  python training/rollout-loop-20261113/label_variant.py IN.npz OUT.npz [--k K] [--rows FRACTION] [--seed S]

--k K           the labels of a bot with only the first K recorded layouts: `gap` becomes `gap_kK` and the card the
                policy learns (meta column 0) becomes `card_kK`
--rows FRACTION keep this share of each deal's rows, drawn at random (the same deals, fewer positions of each)

Per-row arrays are cut together; the per-deal and fixed arrays are kept as they are. The K-variant arrays are dropped.
"""
import argparse
from pathlib import Path
import numpy as np

PER_ROW = ('state', 'order', 'legal', 'ctx', 'auction', 'shown', 'gap', 'owner', 'meta', 'deal', 'sid', 'sid_floor', 'sid_ceil')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('src', type=Path)
    p.add_argument('out', type=Path)
    p.add_argument('--k', type=int, default=0)
    p.add_argument('--rows', type=float, default=1.)
    p.add_argument('--seed', type=int, default=0)
    a = p.parse_args()
    with np.load(a.src, allow_pickle=True) as z:
        data = {k: z[k] for k in z.files}
    extra = [k for k in data if k.startswith(('gap_k', 'card_k', 'full_k'))]
    if a.k:
        if f'gap_k{a.k}' not in data:
            raise SystemExit(f'{a.src} has no labels for k={a.k} (have {sorted(extra)})')
        data['gap'] = data[f'gap_k{a.k}']
        data['meta'] = data['meta'].copy()
        changed = int((data['meta'][:, 0] != data[f'card_k{a.k}']).sum())
        data['meta'][:, 0] = data[f'card_k{a.k}']
        print(f'k={a.k}: {changed} of {len(data["meta"])} rows learn another card; {int(data[f"full_k{a.k}"].sum())} kept the full labels')
    for k in extra:
        del data[k]
    n = len(data['deal'])
    if a.rows < 1:
        keep = np.random.default_rng(a.seed).random(n) < a.rows
        for k in PER_ROW:
            if k in data:
                data[k] = data[k][keep]
        print(f'rows: kept {int(keep.sum())} of {n}, deals with any row {len(np.unique(data["deal"]))}')
    np.savez(a.out, **data)


if __name__ == '__main__':
    main()
