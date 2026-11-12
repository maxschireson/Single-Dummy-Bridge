#!/usr/bin/env python3
"""Do a decision's outcomes swing on two or three hidden variables?

  python scripts/plan_family_study.py --episodes DIR_OR_LIST --net PATH [--layouts 128] [--margin 0.5]
        [--from-trick 2] [--to-trick 6] [--decisions 500] [--workers 2] [--out rows.json]

At recorded Gen 6 decisions that carried a gap fork, --layouts layouts are drawn from Gen 6's exact
class posterior (gen6.Classes with the hand-fit scorer) and every legal card is solved in each. The
candidates are the cards plain search rates within --margin tricks of its best (cards the solves cannot
tell apart count once). For three kinds of outcome, one row per layout:

  dd        double-dummy tricks of each candidate, minus the layout's mean over candidates
            (so "this layout is just good or bad" is removed and what is left is which card is right)
  playout   the same from playing each layout out with the net at every seat (the first three candidates)
  change    playout minus double dummy, card by card: what honest play changes

the script finds the best one, two and three yes/no variables about the hidden hands (who holds a
given honour, whether a hand has at least k cards of a suit; bridge_harness/plan_families.py) and
reports the share of the outcome's spread they explain, on layouts the variables were not chosen on.
It also compares each family's exact weight (a sum over classes) with its share of 32 drawn layouts.
"""
import argparse
import gzip
import json
from multiprocessing import Pool
import os
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from bridge_harness.core import Board, Game, card, symbol
from bridge_harness.gen6 import Classes, View, _merge, spaced
from bridge_harness.gen7 import player
from bridge_harness.gen7_net import PolicyNet
from bridge_harness.plan_families import Features, held_out, key_variables
from bridge_harness.plan_rollout import NetPlayer, Public, card_values
import gen7_check as check

STATE = {}


def start(net, layouts, margin, from_trick, to_trick, seed):
    os.environ['BRIDGE_DDS_CACHE'] = ''
    six = player(check.spec('gen6'), ROOT)
    STATE.update(six=six, net=PolicyNet(Path(net).resolve(), six.scorer), layouts=layouts, margin=margin, from_trick=from_trick,
                 to_trick=to_trick, seed=seed)


def decisions_of(path):
    six, net, out = STATE['six'], STATE['net'], []
    with gzip.open(path, 'rt') as f:
        d = json.load(f)
    for key, e in d['unique_tables'].items():
        if 'tables' not in e:
            continue
        plies = sorted({g['ply'] for g in e.get('gap_forks') or [] if STATE['from_trick'] <= g['ply'] // 4 + 1 <= STATE['to_trick'] and g['ply'] > 0})
        if not plies:
            continue
        board = Board.from_dict(e['board'])
        root = e['tables'][0]
        for ply in plies:
            if not root['actions'][ply].get('gen6'):
                continue
            game = Game(board)
            for x in root['actions'][:ply]:
                game.play(card(x['card']))
            o = game.observation()
            view = View(o)
            if len(view.hidden) != 2 or six.source(o, view) != 'scorer':
                continue
            rng = np.random.default_rng([STATE['seed'], ply, int(d['family'][:8], 16)])
            classes = Classes(view)
            logw = classes.logmult + six.type_log_weights(o, view, classes.length, classes.hon, 'scorer')
            pw = np.exp(logw - logw.max())
            pw /= pw.sum()
            worlds, weights = _merge(classes.worlds(spaced(logw, STATE['layouts'], rng.random()), rng))
            weights = np.asarray(weights, float)
            legal = list(o.legal)
            u = np.array([[x[c] for c in legal] for x in (check.utilities(o, values) for values, _ in check.solve(six, o, worlds))], float)
            groups = {}
            for j, c in enumerate(legal):
                groups.setdefault((c // 13, u[:, j].tobytes()), []).append(j)
            reps = [g[0] for g in groups.values()]
            value = weights @ u[:, reps]
            order = np.argsort(-value)
            near = [reps[i] for i in order if value[order[0]] - value[i] <= STATE['margin'] + 1e-9]
            row = dict(family=d['family'], ply=ply, trick=ply // 4 + 1, declaring=o.controller % 2 == o.contract.declarer % 2, legal=len(legal),
                       distinct=len(reps), candidates=len(near), classes=len(classes), layouts=len(worlds),
                       fused=float(weights @ u.max(axis=1) - value.max()))
            if len(near) < 2:
                out.append(row)
                continue
            feats = Features(view)
            x = feats.of(worlds)
            xc = feats.of_classes(classes)
            cards = [legal[j] for j in near]
            row['cards'] = [symbol(c) for c in cards]
            row['gaps'] = [float(value.max() - weights @ u[:, j]) for j in near]
            dd = u[:, near]
            outcomes = dict(dd=dd - dd.mean(axis=1, keepdims=True))
            top = cards[:3]
            started = time.perf_counter()
            roll = card_values(o, worlds, top, NetPlayer(net, 'top'), Public(net, o))
            row['seconds_playout'] = time.perf_counter() - started
            outcomes['playout'] = roll - roll.mean(axis=1, keepdims=True)
            outcomes['change'] = roll - dd[:, :len(top)]
            outcomes['change2'] = (roll[:, 0] - roll[:, 1]) - (dd[:, 0] - dd[:, 1])
            row['pimc_gap'] = float(weights @ (dd[:, 0] - dd[:, 1]))
            row['playout_gap'] = float(weights @ (roll[:, 0] - roll[:, 1]))
            for name, y in outcomes.items():
                yy = y if y.ndim == 2 else y[:, None]
                sd = float(np.sqrt((weights[:, None] * (yy - weights @ yy) ** 2).sum()))
                key = key_variables(x, y, weights)
                row[name] = dict(sd=sd, variables=[feats.names[v] for v in key.variables], explained=[round(float(v), 4) for v in key.explained],
                                 held_out=[round(float(v), 4) for v in held_out(x, y, weights)])
                if name == 'dd' and key.variables:
                    # exact family weights against the share of 32 spaced draws, for the two-variable families
                    fam_c = key.families(xc, 2)
                    exact = np.bincount(fam_c, weights=pw, minlength=4)
                    drawn = np.bincount(key.families(feats.of(classes.worlds(spaced(logw, 32, rng.random()), rng)), 2), minlength=4) / 32
                    row['family_exact'] = [round(float(v), 4) for v in exact]
                    row['family_drawn32'] = [round(float(v), 4) for v in drawn]
            out.append(row)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--episodes', type=Path, required=True)
    p.add_argument('--net', type=Path, required=True)
    p.add_argument('--layouts', type=int, default=128)
    p.add_argument('--margin', type=float, default=.5)
    p.add_argument('--from-trick', type=int, default=2)
    p.add_argument('--to-trick', type=int, default=6)
    p.add_argument('--decisions', type=int, default=10 ** 9)
    p.add_argument('--files', type=int, default=10 ** 9)
    p.add_argument('--workers', type=int, default=2)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    files = sorted(a.episodes.glob('*.json.gz')) if a.episodes.is_dir() else [Path(x) for x in a.episodes.read_text().split()]
    rows, started = [], time.time()
    with Pool(a.workers, initializer=start, initargs=(a.net, a.layouts, a.margin, a.from_trick, a.to_trick, a.seed)) as pool:
        for n, got in enumerate(pool.imap(decisions_of, files[:a.files], chunksize=2), 1):
            rows += got
            if n % 50 == 0:
                print(f'{n} files, {len(rows)} decisions, {round(time.time() - started)} s', flush=True)
            if len(rows) >= a.decisions:
                pool.terminate()
                break
    a.out.write_text(json.dumps(dict(settings=dict(net=str(a.net), layouts=a.layouts, margin=a.margin, from_trick=a.from_trick, to_trick=a.to_trick,
                                                   seed=a.seed, seconds=round(time.time() - started)), rows=rows)))
    close = [r for r in rows if r['candidates'] >= 2]
    print(json.dumps(dict(decisions=len(rows), with_two_candidates=len(close))))
    for name in ('dd', 'playout', 'change', 'change2'):
        got = [r[name] for r in close if r[name]['held_out']]
        if not got:
            continue
        h = np.array([g['held_out'] + [g['held_out'][-1]] * (4 - len(g['held_out'])) for g in got])
        sd = np.array([g['sd'] for g in got])
        print(f"{name:8s} decisions {len(got):5d} | sd {sd.mean():.3f} | held-out share explained by 1, 2, 3 variables: mean "
              + ' '.join(f'{v:.2f}' for v in h[:, 1:].mean(axis=0)) + ' | weighted by spread: '
              + ' '.join(f'{v:.2f}' for v in (h[:, 1:] * (sd ** 2)[:, None]).sum(axis=0) / (sd ** 2).sum())
              + ' | median ' + ' '.join(f'{v:.2f}' for v in np.median(h[:, 1:], axis=0)))


if __name__ == '__main__':
    main()
