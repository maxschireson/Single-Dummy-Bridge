#!/usr/bin/env python3
"""What does a simulated seat give up when it DRAWS its card from a net, as the rollouts' seats do (`seat: draw`), against
when it plays the net's most probable card? On held-out rows with a value for the cards (the rollouts' values on pure
Stu's rows, rated candidates only; the search's gap on a search bot's rows, every legal card):

  python training/rollout-loop-20261113/draw_regret.py ROWS.npz --bot stup0 NAME=NET.npz:OWN:OTHER [NAME=...]

Each net is told that the side to play is OWN and the other side OTHER (names in its vocabulary; leave both empty for a
net that takes no names), on every row: what a bot's `x8.names` tell its simulated seats. For each net, by phase:

  top      tricks given up by its most probable card (nan where the rollouts did not rate that card)
  draw     expected tricks given up by a card drawn from its probabilities, among the rated cards, and (after the
           slash) the percentage of draws that are cards the rollouts did not rate (0 on a search bot's rows)
  draw^2   the same with the probabilities squared and renormalised (a sharper draw: `power` 2)
  cut.x    the same for a draw among the cards at least x times as likely as the likeliest (the seats' `cut`)
  nats     the entropy of its probabilities over the legal cards
and, for each net after the first, draw minus the first net's draw on the same rows (paired, SE clustered by deal).
"""
import argparse, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from bridge_harness.gen7_net import INPUTS, PolicyNet  # noqa: E402

PHASES = ('lead', 'tricks 1-4', 'tricks 5-8', 'tricks 9-13', 'all')
WAYS = (('draw', 1., 0.), ('draw^2', 2., 0.), ('cut.1', 1., .1), ('cut.25', 1., .25), ('cut.5', 1., .5))


def phase_of(ply):
    trick = ply // 4 + 1
    return np.where(ply == 0, 0, np.where(trick <= 4, 1, np.where(trick <= 8, 2, 3)))


def clustered(d, groups):
    u, inv = np.unique(groups, return_inverse=True)
    s, n = np.bincount(inv, d), np.bincount(inv)
    mean = s.sum() / n.sum()
    g = len(u)
    return float(mean), float(np.sqrt(g / max(g - 1, 1) * ((s - mean * n) ** 2).sum()) / n.sum())


def stats(net, own, other, data):
    batch = {k: data[k] for k in INPUTS}
    n = len(data['deal'])
    if net.vocab:
        batch['bot_own'] = np.full(n, net.bot_id(own), np.int32)
        batch['bot_other'] = np.full(n, net.bot_id(other), np.int32)
    logp = net.log_policy_arrays(batch).astype(np.float64)
    legal = data['legal'].astype(bool)
    p = np.where(legal, np.exp(logp), 0.)
    p /= p.sum(1, keepdims=True)
    gap = data['gap'].astype(np.float64)
    rated = legal & (gap >= 0)
    g = np.where(rated, gap, 0.)
    rows = np.arange(n)
    pick = np.where(legal, p, -1.).argmax(1)
    out = dict(top=np.where(rated[rows, pick], gap[rows, pick], np.nan))
    for name, q, cut in WAYS:
        w = p ** q
        if cut:
            w = np.where(w >= cut * w.max(1, keepdims=True), w, 0.)
        w /= w.sum(1, keepdims=True)
        mass = (w * rated).sum(1)
        out[name] = (w * g).sum(1) / np.maximum(mass, 1e-12)
        out[name + ' unrated'] = 1. - mass
    out['nats'] = -(np.where(p > 0, p * np.log(np.maximum(p, 1e-300)), 0.)).sum(1)
    return out


def main():
    a = argparse.ArgumentParser()
    a.add_argument('rows', type=Path)
    a.add_argument('specs', nargs='+')
    a.add_argument('--bot', default='stup0')
    a = a.parse_args()
    with np.load(a.rows, allow_pickle=True) as z:
        data = {k: np.array(z[k]) for k in (*INPUTS, 'gap', 'meta', 'deal')}
        names = [str(x) for x in z['bot_names']]
    meta = data['meta']
    mine = (meta[:, 8] == names.index(a.bot)) & (meta[:, 10] == 1)
    data = {k: v[mine] for k, v in data.items()}
    phase = phase_of(data['meta'][:, 3])
    print(f'{a.rows.name}: {int(mine.sum())} rows of {a.bot} with values, {len(np.unique(data["deal"]))} deals')
    first = None
    for spec in a.specs:
        name, rest = spec.split('=', 1)
        path, own, other = (rest.split(':') + ['', ''])[:3]
        s = stats(PolicyNet(path, None), own, other, data)
        print(f'-- {name} (told {own or "nothing"}/{other or "nothing"})')
        print('   phase         rows    top  ' + '  '.join(f'{name:>11s}' for name, _, _ in WAYS) + '   nats'
              + ('   draw minus the first net (paired)' if first else ''))
        for i, ph in enumerate(PHASES):
            m = phase == i if i < 4 else np.ones(len(phase), bool)
            if not m.any():
                continue
            line = f'   {ph:12s} {int(m.sum()):5d}  {np.nanmean(s["top"][m]):.4f}  ' + '  '.join(
                f'{s[name][m].mean():.4f}/{100 * s[name + " unrated"][m].mean():4.1f}' for name, _, _ in WAYS) + f'  {s["nats"][m].mean():.3f}'
            if first is not None:
                d, se = clustered((s['draw'] - first['draw'])[m], data['deal'][m])
                line += f'   {d:+.4f} +- {se:.4f}'
            print(line)
        first = first or s


if __name__ == '__main__':
    main()
