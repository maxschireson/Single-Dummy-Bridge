#!/usr/bin/env python3
"""A random sample of whole deals of a built set, as a small set of its own.

  python training/rollout-loop-20261113/sample_set.py BIG.npz OUT.npz --rows N [--seed 0] [--bots NAME[,NAME...]]

Round 1 trains on Stu's rows together with rows of the bots the net already knows, so that it keeps its model of
them. This draws those rows: deals of BIG at random, without replacement, until they hold at least N rows. Every row
of a drawn deal is kept, in BIG's order, with the deals renumbered; the bots' names and every other array are BIG's.
--bots keeps only the rows those bots decided (the deciding side's bot, meta column 8), from the drawn deals that have
any; deals are drawn until those rows reach N (all of them when N is larger than they come to).
BIG is read through memory maps (it must be stored uncompressed, as scripts/gen7_build_dataset.py and merge_sets.py
write it), so a 23 GB set costs the memory of its `deal` column and of the sample.
"""
import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ROWS = ('state', 'order', 'legal', 'ctx', 'auction', 'shown', 'gap', 'owner', 'meta')
FIXED = ('bank_length', 'bank_hon', 'bank_log_weight', 'meta_columns', 'bot_names')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('big', type=Path)
    p.add_argument('out', type=Path)
    p.add_argument('--rows', type=int, required=True)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--bots', default='')
    a = p.parse_args()
    spec = importlib.util.spec_from_file_location('train_rollout_net', ROOT / 'scripts' / 'train_rollout_net.py')
    trainer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(trainer)
    z = trainer.stored_arrays(a.big)
    deal = np.asarray(z['deal'])
    keep = np.ones(len(deal), bool)
    if a.bots:
        names = [str(x) for x in z['bot_names']]
        wanted = [names.index(b) for b in a.bots.split(',')]
        keep = np.isin(np.asarray(z['meta'][:, 8]), wanted)
    count = np.bincount(deal[keep], minlength=len(z['family']))
    order = np.random.default_rng(a.seed).permutation(len(count))
    k = int(np.searchsorted(np.cumsum(count[order]), a.rows)) + 1
    chosen = np.sort(order[:k])
    chosen = chosen[count[chosen] > 0]
    rows = np.flatnonzero(np.isin(deal, chosen) & keep)
    index = np.full(len(count), -1, np.int64)
    index[chosen] = np.arange(len(chosen))
    out = {name: np.asarray(z[name][rows]) for name in ROWS}
    out['deal'] = index[deal[rows]].astype(np.int32)
    out['family'] = np.asarray(z['family'])[chosen]
    out['deal_split'] = np.asarray(z['deal_split'])[chosen]
    for name in FIXED:
        out[name] = np.asarray(z[name])
    np.savez(a.out, **out)
    names = [str(x) for x in out['bot_names']]
    by = np.bincount(out['meta'][:, 8], minlength=len(names))
    print(json.dumps(dict(deals=len(chosen), of=len(count), examples=len(rows), asked=a.rows, seed=a.seed,
                          rows_by_bot={n: int(c) for n, c in zip(names, by) if c})))


if __name__ == '__main__':
    main()
