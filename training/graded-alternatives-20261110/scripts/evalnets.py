"""DD-scored duplicate comparisons between saved bidders on named deal sets.

usage: evalnets.py SET[,SET...] NAME=path [NAME=path ...] -- A:B [A:B ...]
sets: select (train deals 35000-39999 + dev), hold, dev, review, train35k, fresh (data/fresh_test.jsonl)
Each A:B plays A against B in both rooms. With several comparisons against the same opponent the
per-deal paired differences are also reported.
"""
import itertools
import json
import os
import sys

os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
import numpy as np

sys.path.insert(0, '/home/claude/gen5r')
sys.path.insert(0, '/home/claude/bid')
import abid  # noqa: E402
from bridge_harness.bidding_ppo import Policy  # noqa: E402

D = '/home/claude/bid/data'


def join(x, y):
    d = object.__new__(abid.Deals)
    d.hands, d.vul = x.hands + y.hands, x.vul + y.vul
    d.dealer, d.table = np.concatenate([x.dealer, y.dealer]), np.concatenate([x.table, y.table])
    d.static, d.vulflag = np.concatenate([x.static, y.static]), np.concatenate([x.vulflag, y.vulflag])
    return d


_train = None


def train():
    global _train
    if _train is None:
        _train = abid.Deals.from_export(f'{D}/train.jsonl.gz')
    return _train


def load_set(name):
    if name == 'hold':
        return train().subset(np.arange(35000, 40000))
    if name == 'dev':
        return abid.Deals.from_export(f'{D}/dev.jsonl.gz')
    if name == 'select':
        return join(load_set('hold'), load_set('dev'))
    if name == 'train35k':
        return train().subset(np.arange(35000))
    if name == 'review':
        return abid.Deals.from_solved(f'{D}/review_test.jsonl')
    if name == 'fresh':
        return abid.Deals.from_solved(f'{D}/fresh_test_prefix.jsonl')
    if name == 'alltest':
        return join(load_set('review'), load_set('fresh'))
    raise SystemExit(f'unknown set {name}')


def main():
    args = sys.argv[1:]
    cut = args.index('--')
    sets, nets, pairs = args[0].split(','), dict(a.split('=', 1) for a in args[1:cut]), [a.split(':') for a in args[cut + 1:]]
    pol = {k: Policy.load(v) for k, v in nets.items()}
    for s in sets:
        deals = load_set(s)
        res = {}
        for a, b in pairs:
            r, _ = abid.duplicate(deals, pol[a], pol[b])
            res[(a, b)] = r
            m = abid.summary(r)
            print(json.dumps(dict(set=s, a=a, b=b, n=m['n'], total=m['total'], mean=round(m['mean'], 4), se=round(m['se'], 4),
                                  wins=m['wins'], losses=m['losses'], ties=m['ties'])), flush=True)
        for (k1, r1), (k2, r2) in itertools.combinations(res.items(), 2):
            if k1[1] == k2[1]:
                d = (r1 - r2).astype(float)
                print(json.dumps(dict(set=s, paired=f'{k1[0]} minus {k2[0]} (both vs {k1[1]})', mean=round(float(d.mean()), 4),
                                      se=round(float(d.std(ddof=1) / np.sqrt(len(d))), 4))), flush=True)


if __name__ == '__main__':
    main()
