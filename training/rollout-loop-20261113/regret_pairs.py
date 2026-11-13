#!/usr/bin/env python3
"""Indicator 1 of PLAN.md with its standard error: on held-out rows, the tricks a net's first card gives up against the
rollouts' values, for one bot's decisions by phase, for two nets on the same rows.

  python training/rollout-loop-20261113/regret_pairs.py VAL.npz BEFORE.npz AFTER.npz [--bot stup0] [--as stup0=stu0]

The rows and the score are train_rollout_net.evaluate's: rows the bot's rollouts searched, the net's most probable
card, its gap (tricks below the best rated card) where the rollouts rated that card. Each net's own mean is over the
rows where its card was rated (as the trainer reports it); the difference is over the rows where both were, paired,
with a standard error clustered by deal (rows of one board are not independent). --as NEW=OLD: a net that lacks bot
NEW reads it as OLD (round 1's net has stu0, not stup0, and the trainer starts stup0 from stu0's vectors).
"""
import argparse, json, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from bridge_harness.gen7_net import INPUTS, PolicyNet  # noqa: E402

PHASES = ('lead', 'tricks 1-4', 'tricks 5-8', 'tricks 9-13')


def phase_of(ply):
    trick = ply // 4 + 1
    return np.where(ply == 0, 0, np.where(trick <= 4, 1, np.where(trick <= 8, 2, 3)))


def regret(net, data, names, alias):
    """[rows] gap of the net's most probable card, nan where the rollouts did not rate it."""
    table = np.array([net.bot_id(n if n in net.vocab else alias.get(n, n)) for n in names], np.int32)
    meta = data['meta']
    batch = {k: data[k] for k in INPUTS}
    batch['bot_own'], batch['bot_other'] = table[meta[:, 8]], table[meta[:, 9]]
    logp = net.log_policy_arrays(batch)
    pick = logp.argmax(1)
    rows = np.arange(len(pick))
    gap = data['gap'].astype(np.float64)
    rated = data['legal'].astype(bool) & (gap >= 0)
    return np.where(rated[rows, pick], gap[rows, pick], np.nan)


def clustered(d, groups):
    """Mean of d and its standard error with rows clustered by group."""
    u, inv = np.unique(groups, return_inverse=True)
    s, n = np.bincount(inv, d), np.bincount(inv)
    mean = s.sum() / n.sum()
    g = len(u)
    se = np.sqrt(g / max(g - 1, 1) * ((s - mean * n) ** 2).sum()) / n.sum()
    return float(mean), float(se)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('val', type=Path)
    p.add_argument('before', type=Path)
    p.add_argument('after', type=Path)
    p.add_argument('--bot', default='stup0')
    p.add_argument('--as', dest='alias', default='stup0=stu0')
    p.add_argument('--json', type=Path)
    a = p.parse_args()
    alias = dict(x.split('=', 1) for x in a.alias.split(',') if x)
    with np.load(a.val, allow_pickle=True) as z:
        data = {k: np.array(z[k]) for k in (*INPUTS, 'gap', 'legal', 'meta', 'deal') if k in z.files}
        names = [str(x) for x in z['bot_names']]
    if 'legal' not in data:
        raise SystemExit(f'{a.val} has no legal cards')
    r0 = regret(PolicyNet(a.before, None), data, names, alias)
    r1 = regret(PolicyNet(a.after, None), data, names, alias)
    meta = data['meta']
    mine = (meta[:, 8] == names.index(a.bot)) & (meta[:, 10] == 1)
    phase = phase_of(meta[:, 3])
    out = {}
    print(f'{a.bot}: {int(mine.sum())} searched held-out rows, {len(np.unique(data["deal"][mine]))} deals')
    print('phase         rows  before   after  after-before (paired, SE by deal)')
    for i, name in enumerate(PHASES + ('all',)):
        m = mine & (phase == i) if i < 4 else mine
        both = m & ~np.isnan(r0) & ~np.isnan(r1)
        if not both.any():
            continue
        b0, b1 = float(np.nanmean(r0[m])), float(np.nanmean(r1[m]))
        diff, se = clustered(r1[both] - r0[both], data['deal'][both])
        out[name] = dict(rows=int(m.sum()), paired=int(both.sum()), before=b0, after=b1, diff=diff, se=se)
        print(f'{name:12s} {int(m.sum()):5d}  {b0:6.4f}  {b1:6.4f}  {diff:+.4f} +- {se:.4f}')
    if a.json:
        a.json.write_text(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
