#!/usr/bin/env python3
"""How well does each seat know where the unseen cards are? The net's owner head against Gen 6's scorer posterior.

  python scripts/plan_belief_check.py --episodes DIR_OR_LIST --nets v0=PATH,v41=PATH [--files 200] [--workers 2]

At every searched decision of the root tables with dummy down and two hands hidden, for each unseen card:
the log-probability given to its true holder by (a) each net's owner head read from the decider's view,
(b) Gen 6's exact class posterior (hand-fit scorer on the auction, card-fit only for the play), tricks 1-6 only.
Also, for the most likely layout by the owner head (the Believer's plan): the share of unseen cards placed right
and how often the whole layout is right. Reported by trick band and by side.
"""
import argparse
import gzip
import json
from multiprocessing import Pool
import os
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from bridge_harness.core import Board, Game, card
from bridge_harness.gen6 import Classes, View
from bridge_harness.gen7 import player
from bridge_harness.gen7_net import PolicyNet, forward, stack
from bridge_harness.plan_families import Features
import gen7_check as check

STATE = {}
BANDS = ((1, 2), (3, 4), (5, 6), (7, 9), (10, 13))


def start(nets):
    os.environ['BRIDGE_DDS_CACHE'] = ''
    six = player(check.spec('gen6'), ROOT)
    STATE.update(six=six, nets={k: PolicyNet(Path(v).resolve(), six.scorer) for k, v in nets.items()})


def log_softmax(x):
    x = x - x.max(axis=-1, keepdims=True)
    return x - np.log(np.exp(x).sum(axis=-1, keepdims=True))


def of_file(path):
    six, out = STATE['six'], []
    with gzip.open(path, 'rt') as f:
        d = json.load(f)
    for e in d['unique_tables'].values():
        if 'tables' not in e:
            continue
        board = Board.from_dict(e['board'])
        game = Game(board)
        for act in e['tables'][0]['actions']:
            o = game.observation()
            c = card(act['card'])
            if o.history and len(o.legal) > 1 and act.get('gen6'):
                view = View(o)
                a, b = view.hidden
                unseen = view.unseen
                truth = np.array([c2 in game.hands[a] for c2 in unseen])
                trick = len(o.history) // 4 + 1
                row = dict(trick=trick, declaring=o.controller % 2 == o.contract.declarer % 2, unseen=len(unseen))
                for name, net in STATE['nets'].items():
                    owner = forward(net.params, stack([net.encode(o)]))['owner'][0]
                    two = log_softmax(np.stack([owner[unseen, (a - o.controller) % 4 - 1], owner[unseen, (b - o.controller) % 4 - 1]], axis=1).astype(np.float64))
                    row[name] = float(np.where(truth, two[:, 0], two[:, 1]).mean())
                    lean = two[:, 0] - two[:, 1]
                    suit = unseen // 13
                    lean = np.where([(a, s) in view.voids for s in suit], -np.inf, np.where([(b, s) in view.voids for s in suit], np.inf, lean))
                    pick = np.zeros(len(unseen), bool)
                    pick[np.argsort(-lean, kind='stable')[:len(game.hands[a])]] = True
                    row[name + '_right'] = float((pick == truth).mean())
                    row[name + '_exact'] = bool((pick == truth).all())
                if trick <= 6 and six.source(o, view) == 'scorer':
                    classes = Classes(view)
                    logw = classes.logmult + six.type_log_weights(o, view, classes.length, classes.hon, 'scorer')
                    w = np.exp(logw - logw.max())
                    w /= w.sum()
                    # marginal probability that hand a holds each unseen card: honours by class, low cards by the class's count
                    p = np.zeros(len(unseen))
                    for s in range(4):
                        op, j = classes.options[s], classes.index[:, s]
                        for t, hc in enumerate(classes.honours[s]):
                            p[list(unseen).index(hc)] = float(w @ ((op['mask'][j] >> t) & 1))
                        low = classes.lows[s]
                        if low:
                            share = float(w @ op['n'][j]) / len(low)
                            for lc in low:
                                p[list(unseen).index(lc)] = share
                    p = p.clip(1e-6, 1 - 1e-6)
                    row['scorer'] = float(np.where(truth, np.log(p), np.log(1 - p)).mean())
                row['uniform'] = float(np.where(truth, np.log(len(game.hands[a]) / len(unseen)), np.log(len(game.hands[b]) / len(unseen))).mean())
                out.append(row)
            game.play(c)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--episodes', type=Path, required=True)
    p.add_argument('--nets', required=True)
    p.add_argument('--files', type=int, default=200)
    p.add_argument('--workers', type=int, default=2)
    a = p.parse_args()
    nets = dict(item.split('=') for item in a.nets.split(','))
    files = sorted(a.episodes.glob('*.json.gz')) if a.episodes.is_dir() else [Path(x) for x in a.episodes.read_text().split()]
    rows = []
    with Pool(a.workers, initializer=start, initargs=(nets,)) as pool:
        for got in pool.imap(of_file, files[:a.files], chunksize=4):
            rows += got
    names = ['uniform', 'scorer', *nets]
    print(f'{len(rows)} decisions on {min(a.files, len(files))} boards. Mean log-probability of the true holder, per unseen card (nats; higher is better):')
    print(f"{'tricks':8s} {'n':>6s} " + ' '.join(f'{n:>9s}' for n in names) + ' | most likely layout: cards right, whole layout right: ' + ' '.join(nets))
    for lo, hi in BANDS:
        sub = [r for r in rows if lo <= r['trick'] <= hi]
        if not sub:
            continue
        cells = []
        for n in names:
            v = [r[n] for r in sub if n in r]
            cells.append(f'{np.mean(v):9.4f}' if v else f"{'':9s}")
        extra = ' '.join(f"{np.mean([r[n + '_right'] for r in sub]):.3f},{np.mean([r[n + '_exact'] for r in sub]):.3f}" for n in nets)
        print(f'{lo}-{hi:<6d} {len(sub):6d} ' + ' '.join(cells) + ' | ' + extra)


if __name__ == '__main__':
    main()
