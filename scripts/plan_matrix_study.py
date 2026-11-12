#!/usr/bin/env python3
"""Plans against layouts: is choosing a whole plan worth anything, inside the simulator?

  python scripts/plan_matrix_study.py --episodes DIR_OR_LIST --net PATH [--margin 0.25] [--plans 6]
        [--from-trick 3] [--to-trick 6] [--decisions 300] [--workers 2] [--out rows.json]

At recorded Gen 6 decisions with at least two cards within --margin of the search's best:

  layouts   Gen 6's own (32, with their weights)
  cards     the near-best cards, at most three (cards the solves cannot tell apart count once)
  plans     the default line (play for the likeliest layout that still fits) and one plan per layout family:
            "play for the likeliest layout of this family that still fits, until none does" (plan_rollout.Planner).
            Families are the joint values of the decision's key variables (plan_families), the heaviest --plans.

and the matrix M[card, plan, layout] of final tricks is filled by playouts in which the decider's side follows
the plan and every other seat plays the solver's card for its own most likely layout (plan_rollout.Believer).
Every row of the matrix is one consistent strategy for the decider, so a weighted row mean is an honest value
of that strategy against these simulated opponents. Reported per decision, choosing on half the layouts and
scoring on the other half (both ways, averaged), so that picking the best of many rows does not flatter itself:

  card       gain from choosing the card by playout value, default line after it
  plan       gain from choosing the plan, the search's card first
  both       gain from choosing card and plan together
  each in tricks and in IMPs against the search's card with the default line in the same layout.

This is a necessary test, not a sufficient one: the opponents here are simulated. Played boards decide.
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
from bridge_harness.core import Board, Game, card, imps, score, symbol, vulnerable
from bridge_harness.gen6 import View
from bridge_harness.gen7 import player
from bridge_harness.gen7_net import PolicyNet
from bridge_harness.plan_families import Features, key_variables
from bridge_harness.plan_rollout import Public, plan_values
import gen7_check as check

STATE = {}


def start(net, margin, plans, from_trick, to_trick, seed, own_layouts):
    os.environ['BRIDGE_DDS_CACHE'] = ''
    six = player(check.spec('gen6'), ROOT)
    STATE.update(six=six, net=PolicyNet(Path(net).resolve(), six.scorer), margin=margin, plans=plans, from_trick=from_trick, to_trick=to_trick, seed=seed,
                 own_layouts=own_layouts)


def split_gain(value, weights, base):
    """Choose the best row of value[rows, layouts] on half the layouts, score it on the other half against row
    `base`; both ways, averaged. Also the gain without the split (optimistic)."""
    out = 0.
    for s in (0, 1):
        train, test = np.arange(len(weights)) % 2 == s, np.arange(len(weights)) % 2 != s
        if weights[train].sum() <= 0 or weights[test].sum() <= 0:
            return 0., 0.
        pick = int(np.argmax(value[:, train] @ weights[train]))
        out += float((value[pick, test] - value[base, test]) @ weights[test] / weights[test].sum()) / 2
    full = value @ weights
    return out, float(full.max() - full[base])


def decisions_of(path):
    six, net, out = STATE['six'], STATE['net'], []
    with gzip.open(path, 'rt') as f:
        d = json.load(f)
    for key, e in d['unique_tables'].items():
        if 'tables' not in e:
            continue
        plies = sorted({g['ply'] for g in e.get('gap_forks') or [] if STATE['from_trick'] <= g['ply'] // 4 + 1 <= STATE['to_trick'] and g['ply'] > 0})
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
            rng = np.random.default_rng([STATE['seed'], ply, int(d['family'][:8], 16)])
            worlds, weights, _ = six.layouts(o, view, six.source(o, view), rng)
            weights = np.asarray(weights, float)
            legal = list(o.legal)
            u = np.array([[x[c] for c in legal] for x in (check.utilities(o, values) for values, _ in check.solve(six, o, worlds))], float)
            groups = {}
            for j, c in enumerate(legal):
                groups.setdefault((c // 13, u[:, j].tobytes()), []).append(j)
            reps = [g[0] for g in groups.values()]
            value = weights @ u[:, reps]
            order = np.argsort(-value, kind='stable')
            near = [reps[i] for i in order if value[order[0]] - value[i] <= STATE['margin'] + 1e-9][:3]
            row = dict(family=d['family'], ply=ply, trick=ply // 4 + 1, declaring=o.controller % 2 == o.contract.declarer % 2, layouts=len(worlds),
                       candidates=len(near))
            if len(near) < 2 or len(view.hidden) != 2:
                out.append(row)
                continue
            cards = [legal[j] for j in near]
            dd = u[:, near]
            feats = Features(view)
            x = feats.of(worlds)
            key = key_variables(x, dd - dd.mean(axis=1, keepdims=True), weights)
            fam = key.families(x)
            heavy = sorted(set(int(f) for f in fam), key=lambda f: -weights[fam == f].sum())[:STATE['plans']]
            plans = [-1, *heavy] if len(heavy) > 1 else [-1]
            started = time.perf_counter()
            m, who = plan_values(o, worlds, weights, cards, plans, net, six.dds, fam, Public(net, o), own_layouts=STATE['own_layouts'])
            seconds = time.perf_counter() - started
            c = o.contract
            vul = vulnerable(o.vulnerability, c.declarer)
            sign = 1 if row['declaring'] else -1
            points = np.vectorize(lambda t: sign * score(c, int(round(sign * t)), vul))(m)          # the decider's side's score
            swing = np.vectorize(imps)(points - points[0, 0][None, None, :])                           # against the search's card, default line
            w = weights / weights.sum()
            row.update(cards=[symbol(c2) for c2 in cards], gaps=[float(value.max() - weights @ u[:, j]) for j in near], plans=len(plans),
                       variables=[feats.names[v] for v in key.variables], explained=[round(float(v), 3) for v in key.explained],
                       family_weights=[round(float(weights[fam == f].sum()), 3) for f in heavy],
                       # for the search's card: the plan for each family (rows) scored in each family (columns), default line first
                       by_family=[[round(float(m[0, z][fam == g] @ weights[fam == g] / weights[fam == g].sum()), 3) for g in heavy] for z in range(len(plans))],
                       seconds=seconds, solves=who.solves, own_choices=who.own_choices, refuted=who.refuted,
                       dd=[float(v) for v in w @ dd], default=[float(v) for v in m[:, 0, :] @ w],
                       best_plan=[float(v) for v in (m @ w).max(axis=1)])
            for name, table in (('tricks', m), ('imps', swing)):
                n_c, n_z, n_w = table.shape
                row[name] = dict(card=split_gain(table[:, 0, :], w, 0), plan=split_gain(table[0], w, 0),
                                 both=split_gain(table.reshape(n_c * n_z, n_w), w, 0))
            out.append(row)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--episodes', type=Path, required=True)
    p.add_argument('--net', type=Path, required=True)
    p.add_argument('--margin', type=float, default=.25)
    p.add_argument('--plans', type=int, default=6)
    p.add_argument('--own-layouts', type=int, default=1, help="layouts of the plan the decider's later cards are searched over")
    p.add_argument('--from-trick', type=int, default=3)
    p.add_argument('--to-trick', type=int, default=6)
    p.add_argument('--decisions', type=int, default=10 ** 9)
    p.add_argument('--files', type=int, default=10 ** 9)
    p.add_argument('--workers', type=int, default=2)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    files = sorted(a.episodes.glob('*.json.gz')) if a.episodes.is_dir() else [Path(x) for x in a.episodes.read_text().split()]
    rows, started = [], time.time()

    def save():
        a.out.write_text(json.dumps(dict(settings=dict(net=str(a.net), margin=a.margin, plans=a.plans, own_layouts=a.own_layouts, from_trick=a.from_trick, to_trick=a.to_trick,
                                                       seed=a.seed, seconds=round(time.time() - started)), rows=rows)))

    with Pool(a.workers, initializer=start, initargs=(a.net, a.margin, a.plans, a.from_trick, a.to_trick, a.seed, a.own_layouts)) as pool:
        for n, got in enumerate(pool.imap(decisions_of, files[:a.files], chunksize=1), 1):
            rows += got
            if n % 20 == 0:
                print(f'{n} files, {len(rows)} decisions, {sum(1 for r in rows if "tricks" in r)} with a matrix, {round(time.time() - started)} s', flush=True)
                save()
            if sum(1 for r in rows if 'tricks' in r) >= a.decisions:
                pool.terminate()
                break
    save()
    summarize(rows)


def summarize(rows):
    done = [r for r in rows if 'tricks' in r]
    print(json.dumps(dict(decisions=len(rows), with_a_matrix=len(done))))
    if not done:
        return
    fam = [r['family'] for r in done]

    def clustered(x):
        by = {}
        for v, f in zip(x, fam):
            by.setdefault(f, []).append(v)
        t, c = np.array([sum(v) for v in by.values()]), np.array([len(v) for v in by.values()])
        mean = t.sum() / c.sum()
        return mean, float(np.sqrt(((t - mean * c) ** 2).sum() * len(by) / max(1, len(by) - 1)) / c.sum())

    print(f"per decision with a matrix: {np.mean([r['plans'] for r in done]):.1f} plans, {np.mean([r['seconds'] for r in done]):.1f} s, "
          f"{np.mean([r['solves'] for r in done]):.0f} solves; a plan was refuted at {sum(r['refuted'] for r in done) / max(1, sum(r['own_choices'] for r in done)):.2f} of the decider's later choices")
    for unit in ('tricks', 'imps'):
        for what in ('card', 'plan', 'both'):
            held, full = clustered([r[unit][what][0] for r in done]), clustered([r[unit][what][1] for r in done])
            print(f'  {unit:6s} {what:5s}: held-out gain {held[0]:+.4f} +- {held[1]:.4f} a decision (chosen and scored on the same layouts: {full[0]:+.4f})')


if __name__ == '__main__':
    main()
