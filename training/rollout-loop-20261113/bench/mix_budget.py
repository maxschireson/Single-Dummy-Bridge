#!/usr/bin/env python3
"""What would it cost a rollout bot, by its own rollout values, to play a random one of its near-equal candidates?
(Max, 03:45 UTC on 14 November: "we need to randomize ourselves a bit too ... maybe we can spend a quarter imp".)

  python training/rollout-loop-20261113/bench/mix_budget.py EPISODES_DIR [--bot candidate]

For each rollout decision of the bot in the records (two or more candidates): the candidates the race left alive, their
values and the cards of each. For a margin m (`mix.near`), the bot would play any card of the candidates within m of the
best, each alike; the nominal cost is the mean of (best value - the candidate's value) over those cards. Summed over a
board's decisions it is the tricks a board the margin gives up BY THE ROLLOUTS' OWN VALUES. That overstates the real
cost: the best of a few noisy means is partly luck, so some of what is "given up" was never there.
"""
import argparse, glob, gzip, json
from pathlib import Path
import numpy as np

MARGINS = (0., .01, .02, .03, .05, .08, .12, .2)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('episodes', type=Path)
    p.add_argument('--bot', default='candidate', help="'candidate' or 'opponent': whose decisions")
    a = p.parse_args()
    tables, decisions = 0, 0
    cost, hits = {m: 0. for m in MARGINS}, {m: 0 for m in MARGINS}
    for f in sorted(glob.glob(str(a.episodes / '*.json.gz'))):
        d = json.load(gzip.open(f, 'rt'))
        for e in d['unique_tables'].values():
            for t in e.get('tables', []):
                tables += 1
                for act in t['actions']:
                    n = act.get('x8') or {}
                    if (act.get('role') or act.get('player')) != a.bot or n.get('mode') != 'rollout' or len(n.get('cards') or ()) < 2 or 'alive' not in n:
                        continue
                    v = np.array(n['value'], float)
                    alive = [int(j) for j in n['alive']]
                    size = np.array([len(r) for r in n['runs']], float)
                    top = max(v[j] for j in alive)
                    decisions += 1
                    for m in MARGINS:
                        near = [j for j in alive if top - v[j] <= m + 1e-9]
                        cost[m] += float(size[near] @ (top - v[near]) / size[near].sum())
                        hits[m] += len(near) > 1
    print(f'{tables} tables, {decisions} rollout decisions of the {a.bot} with a choice ({decisions / max(tables, 1):.1f} a table)')
    print('margin  share of decisions with 2+ near-equal candidates  nominal tricks given up: a table, a board (two tables)')
    for m in MARGINS:
        print(f'{m:5.2f}   {hits[m] / max(decisions, 1):6.3f}   {cost[m] / max(tables, 1):.4f}   {2 * cost[m] / max(tables, 1):.4f}')


if __name__ == '__main__':
    main()
