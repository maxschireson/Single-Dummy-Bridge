#!/usr/bin/env python3
"""How well does the net predict the next seat's card right after a forced (worse) card, against right after Gen 6's own card?

  python scripts/gen7_reply_check.py EPISODES_DIR POLICY.npz [POLICY2.npz] [--splits=1,2] [--seconds=N]

For every gap fork, the next searched Gen 6 decision after the fork ply is scored twice: in the fork table
(the card before it was forced on the player) and in the root table (the card before it was the search's own).
Scored by Gen 6's own estimates at that decision: tricks the net's most probable card gives up, whether it is an
equal-best card, and whether an equal-best card is in the net's two most probable.
"""
import gzip
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from bridge_harness.core import Board, Game, card
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
    scorer = FitScorer(str(ROOT / check.SCORER))
    nets = [PolicyNet(p, scorer) for p in args[1:]]
    out = {(i, where, lag): [] for i in range(len(nets)) for where in ('fork', 'root') for lag in (1, 2, 3)}
    forks = 0
    import time
    started, limit = time.time(), 1e9
    for a in sys.argv[1:]:
        if a.startswith('--seconds'):
            limit = float(a.split('=')[1])
    for path in sorted(Path(args[0]).glob('*.json.gz')):
        if time.time() - started > limit:
            break
        with gzip.open(path, 'rt') as f:
            d = json.load(f)
        if splits is not None and check.split_of(d['family']) not in splits:
            continue
        for e in d['unique_tables'].values():
            if not e.get('gap_forks'):
                continue
            board = Board.from_dict(e['board'])
            for g in e['gap_forks']:
                ply = g['ply']
                if ply == 0 or not 3 <= ply // 4 + 1 <= 6:
                    continue
                forks += 1
                for where, table in (('fork', e['tables'][g['fork_table']]), ('root', e['tables'][0])):
                    game = Game(board)
                    acts = table['actions']
                    for a in acts[:ply + 1]:
                        game.play(card(a['card']))
                    lag = 0
                    for a in acts[ply + 1:ply + 9]:
                        o = game.observation()
                        if a.get('gen6') and a.get('samples') and len(o.legal) > 1 and a.get('estimates'):
                            lag += 1
                            gaps = np.array([a['estimates'][name(c)]['gap_to_best'] for c in o.legal])
                            if lag <= 3 and gaps.max() > 1e-9:               # a decision with something to lose
                                for i, net in enumerate(nets):
                                    logp = net.log_policy([o])[0][list(o.legal)]
                                    order = np.argsort(-logp)
                                    out[(i, where, lag)].append((gaps[order[0]], gaps[order[0]] <= 1e-9, gaps[order[:2]].min() <= 1e-9,
                                                                 float(np.exp(logp)[gaps <= 1e-9].sum())))
                        if lag >= 3:
                            break
                        game.play(card(a['card']))
    print('gap forks at tricks 3-6:', forks)
    for (i, where, lag), rows in sorted(out.items()):
        if rows:
            x = np.array(rows, float)
            print(f"net {i + 1} | after the {'forced card' if where == 'fork' else 'search card'} | searched decision {lag} later: n {len(x):5d} | gives up {x[:, 0].mean():.4f} +- {x[:, 0].std() / np.sqrt(len(x)):.4f} "
                  f"| equal-best {x[:, 1].mean():.3f} | in top 2 {x[:, 2].mean():.3f} | probability on equal-best cards {x[:, 3].mean():.3f}")


if __name__ == '__main__':
    main()
