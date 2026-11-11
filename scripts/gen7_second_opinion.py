#!/usr/bin/env python3
"""On every gap fork: where the net puts Gen 6's card A and the forced card B, with what really happened.

  python scripts/gen7_second_opinion.py EPISODES_DIR POLICY.npz OUT.json [--splits=1,2]

One row per gap fork at any ply (the opening lead included): ply, band, Gen 6's estimated gap, the probability the
fork was drawn with, the realized cost of B in tricks and IMPs, and the net's probability of A and of B (cards the
search cannot tell apart count as one).
"""
import gzip
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from bridge_harness.core import SEATS, Board, Game, card
from bridge_harness.gen6_nets import FitScorer
from bridge_harness.gen7_net import PolicyNet
import gen7_check as check

name = lambda c: 'SHDC'[c // 13] + '23456789TJQKA'[c % 13]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    splits = None
    for a in sys.argv[1:]:
        if a.startswith('--splits'):
            splits = tuple(int(x) for x in a.split('=')[1].split(','))
    net = PolicyNet(args[1], FitScorer(str(ROOT / check.SCORER)))
    rows, sides = [], 0
    for path in sorted(Path(args[0]).glob('*.json.gz')):
        with gzip.open(path, 'rt') as f:
            d = json.load(f)
        if splits is not None and check.split_of(d['family']) not in splits:
            continue
        for key, e in d['unique_tables'].items():
            if not e.get('gap_forks'):
                continue
            sides += sum(d[who].startswith('6-') for who in ('candidate', 'opponent'))
            board = Board.from_dict(e['board'])
            declarer = board.contract.declarer
            root = e['tables'][0]
            for g in e['gap_forks']:
                ply = g['ply']
                act = root['actions'][ply]
                if not act.get('gen6'):
                    continue
                game = Game(board)
                for a in root['actions'][:ply]:
                    game.play(card(a['card']))
                o = game.observation()
                logp = net.log_policy([o])[0]
                est = act['estimates']
                kind = lambda c: (c // 13, round(est[name(c)]['utility'], 9))
                mass = {}
                for c in o.legal:
                    mass[kind(c)] = mass.get(kind(c), 0.) + float(np.exp(logp[c]))
                order = sorted(mass, key=lambda k: -mass[k])
                a_card, b_card = card(act['card']), card(g['forced_card'])
                seat = SEATS.index(act['seat'])
                sign = 1 if seat % 2 == declarer % 2 else -1
                fork = e['tables'][g['fork_table']]
                rows.append(dict(family=d['family'], table=key, opponent=d['opponent'], ply=ply, band=g['band'], estimated=g['estimated_gap'],
                                 propensity=g['propensity'], final=sign * (root['declarer_tricks'] - fork['declarer_tricks']), imps=g.get('realized_cost_imps'),
                                 p_a=mass[kind(a_card)], p_b=mass[kind(b_card)], rank_a=order.index(kind(a_card)), rank_b=order.index(kind(b_card)),
                                 choices=len(order), draws=act.get('samples')))
    json.dump(dict(sides=sides, rows=rows), open(args[2], 'w'))
    print(len(rows), 'rows', sides, 'sides')


if __name__ == '__main__':
    main()
