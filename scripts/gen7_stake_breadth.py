#!/usr/bin/env python3
"""Breadth by stake, offline: how many cards the net keeps at a decision against the IMPs given up when the
best card is dropped, for a stake-blind rule and a stake-aware one.

Stake of a decision = IMPs that one trick is worth to the side deciding, from the contract and the final trick
count (true stake: the board's realized result; predicted stake: the net's tricks head, averaged over the
results one trick either side). IMPs given up = (Gen 6's gap of the best card kept) x true stake.
  blind:  cards in order of probability until the probabilities add to q
  aware:  cards in order of probability while (probability not yet covered) x predicted stake > theta

  python scripts/gen7_stake_breadth.py DATA SPLIT SOURCE_SET NAME=POLICY ...
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_harness.core import Contract, imps, score
from bridge_harness.gen7_net import INPUTS, forward, log_softmax

data, split, source = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
z = np.load(data)
mask = (z['deal_split'][z['deal']] == split) & ((z['source_set'] == source) if 'source_set' in z.files else True)
rows = np.flatnonzero(mask)
D = {k: z[k][rows] for k in INPUTS}
gap = z['gap'][rows].astype(np.float32); meta = z['meta'][rows]; legal = D['legal']; ctx = D['ctx']; n = len(rows); r = np.arange(n)
deal = z['deal'][rows]; deals, inv = np.unique(deal, return_inverse=True)
strain = 'SHDCN'                                       # ctx[0:4] the trump suit in the encoder's suit order, ctx[4] notrump
level = np.rint(ctx[:, 5] * 7).astype(int); doubled = np.rint(ctx[:, 6] * 2).astype(int); trump = ctx[:, :5].argmax(1)
declaring = meta[:, 6] < 2
decl_vul = np.where(declaring, ctx[:, 17], ctx[:, 18]) > .5
side_tricks = meta[:, 1]
decl_tricks = np.where(declaring, side_tricks, 13 - side_tricks)

table = {}
def swing(lv, tr, db, vul, t):
    """IMPs between declarer taking t and t - 1 tricks."""
    key = (lv, tr, db, vul, t)
    if key not in table:
        c = Contract(int(lv), strain[tr], 0, int(db))
        table[key] = abs(imps(score(c, int(t), bool(vul)) - score(c, int(t) - 1, bool(vul)))) if 1 <= t <= 13 else 0
    return table[key]

def stake_at(t):
    """What a trick is worth to the decider when declarer is headed for t tricks: losing one for declarer, giving one for a defender."""
    return np.array([swing(level[i], trump[i], doubled[i], decl_vul[i], t[i] if declaring[i] else t[i] + 1) for i in range(n)], float)

true_stake = stake_at(decl_tricks)
print(f"{n} decisions, {len(deals)} deals | true stake of a trick, IMPs: mean {true_stake.mean():.2f}, median {np.median(true_stake):.0f}, "
      f"share <= 1: {(true_stake <= 1).mean():.2f}, 5+: {(true_stake >= 5).mean():.2f}, 10+: {(true_stake >= 10).mean():.2f}")
best = legal & (gap <= 1e-9)
for spec in sys.argv[4:]:
    name, path = spec.split('=')
    with np.load(path) as f: params = {k: f[k] for k in f.files}
    outs = [forward(params, {k: v[i:i + 4096] for k, v in D.items()}) for i in range(0, n, 4096)]
    lp = np.concatenate([log_softmax(o['policy']) for o in outs]); th = np.concatenate([np.asarray(o['tricks']).reshape(-1) for o in outs]) * 13
    pred_side = np.clip(np.rint(th), 0, 13).astype(int)
    pred_decl = np.where(declaring, pred_side, 13 - pred_side)
    pred_stake = .5 * stake_at(pred_decl) + .25 * stake_at(np.clip(pred_decl - 1, 0, 13)) + .25 * stake_at(np.clip(pred_decl + 1, 0, 13))
    print(f"== {name}: tricks head off by {np.abs(th - side_tricks).mean():.2f} tricks on average; predicted stake mean {pred_stake.mean():.2f}, "
          f"correlation with the true stake {np.corrcoef(pred_stake, true_stake)[0, 1]:.2f}")
    p = np.exp(np.where(legal, lp, -1e9)); order = np.argsort(-p, axis=1); ps = np.take_along_axis(p, order, 1); cum = np.cumsum(ps, 1)
    before = cum - ps                                   # probability covered before each card in order
    gs = np.take_along_axis(np.where(legal, gap, 99.), order, 1)
    nleg = legal.sum(1)
    runmin = np.minimum.accumulate(gs, axis=1)           # best gap among the first k cards

    def result(k):
        k = np.clip(k, 1, nleg)
        lost = runmin[r, k - 1]
        return k.mean(), lost.mean(), (lost * true_stake).mean(), (lost > 1e-9).mean()
    rowsout = []
    for q in (.5, .7, .8, .85, .9, .93, .95, .97, .98, .99):
        rowsout.append(('blind', q, *result((cum < q).sum(1) + 1)))
    for theta in (2., 1., .7, .5, .35, .25, .18, .12, .08, .05, .03):
        keep = (1 - before) * pred_stake[:, None] > theta          # the first card always: nothing is covered before it
        keep[:, 0] = True
        k = np.where(keep.all(1), 52, (~keep).argmax(1))
        rowsout.append(('aware', theta, *result(k)))
    for theta in (2., 1., .7, .5, .35, .25, .18, .12, .08, .05, .03):
        keep = (1 - before) * true_stake[:, None] > theta
        keep[:, 0] = True
        k = np.where(keep.all(1), 52, (~keep).argmax(1))
        rowsout.append(('aware, true stake', theta, *result(k)))
    for cap in (1, 2, 3):
        rowsout.append((f'top {cap}', cap, *result(np.full(n, cap))))
    print('   rule                 setting  cards kept  tricks given up  IMPs given up  best dropped')
    for rule, setting, kept, tricks, im, miss in rowsout:
        print(f"   {rule:20s} {setting:7.2f} {kept:10.2f} {tricks:15.4f} {im:13.4f} {miss:12.3f}")
    # at equal cards kept: interpolate the blind rule's IMPs at the aware rule's breadth
    blind = sorted((k, im) for rule, s, k, t, im, m in rowsout if rule == 'blind')
    bk, bi = np.array([b[0] for b in blind]), np.array([b[1] for b in blind])
    for which in ('aware', 'aware, true stake'):
        print(f"   {which} against blind at the same cards kept (IMPs given up, and the cut):")
        for rule, s, k, t, im, m in rowsout:
            if rule == which and bk.min() <= k <= bk.max():
                at = float(np.exp(np.interp(k, bk, np.log(bi))))
                print(f"      cards {k:.2f}: aware {im:.4f}, blind {at:.4f}, cut {100 * (1 - im / at):.0f}%")
