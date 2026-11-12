#!/usr/bin/env python3
"""The ceiling of one-step look-ahead: playouts with the real Gen 6 at all four seats, on fork pairs.

  python scripts/plan_ceiling.py --episodes DIR_OR_LIST [--worlds 16] [--from-trick 3] [--to-trick 6]
                                 [--bands 0,1,2] [--pairs N] [--workers 8] [--out rows.json]

scripts/plan_bench.py plays each layout out with the policy net at every seat. Here the simulated
seat is the bot itself: the local Gen 6 (32 layouts, hand-fit scorer, deal list from trick 7), given
only what that seat would see in the layout. So a card's value is what the real bots would take
with it, averaged over the decider's own layouts: the quantity a fork measures once, on the real
deal, measured on --worlds layouts the decider thinks possible. Nothing a player could run at the
table (about a second a playout); it bounds what any faithful simulator can add to plain search.

Rows carry the same fields as plan_bench's, so scripts/plan_report.py reads them (the simulated
player is named `gen6`). `gen6` is pimc plus the playouts' correction on the --worlds layouts, which
are drawn from Gen 6's own in proportion to weight.
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
from bridge_harness.core import SEATS, Board, Game, card, symbol
from bridge_harness.gen6 import View, systematic
from bridge_harness.gen7 import player
from bridge_harness.runner import play_table
import gen7_check as check
import plan_bench

STATE = plan_bench.STATE


def start(from_trick, to_trick, ties, seed, worlds, bands, sim_samples):
    os.environ['BRIDGE_DDS_CACHE'] = ''
    spec = check.spec('gen6')
    if sim_samples:
        spec = dict(spec, samples=sim_samples, id=f'6-{sim_samples}')
    STATE.update(six=player(check.spec('gen6'), ROOT), sim=player(spec, ROOT), sim_id=spec['id'], from_trick=from_trick, to_trick=to_trick,
                 ties=ties, seed=seed, worlds=worlds, bands=bands)


def played_out(o, board, world, x, tag):
    """Declarer's final tricks when the decider plays x in `world` and the simulated bot plays every later card."""
    hands = [tuple(sorted(set(world[s]) | {c for seat, c in o.history if seat == s})) for s in range(4)]
    b = Board(f'{board.id}/{tag}', tuple(hands), board.contract, board.dealer, board.vulnerability, board.auction)
    prefix = [dict(card=symbol(c)) for _, c in o.history] + [dict(card=symbol(x))]
    t = play_table(b, [STATE['sim_id']] * 4, {STATE['sim_id']: STATE['sim']}, seed=STATE['seed'] + 1, prefix=prefix)
    if t['status'] != 'ok':
        raise RuntimeError(t.get('error'))
    return t['declarer_tricks']


def pairs_of(path):
    six, rows = STATE['six'], []
    with gzip.open(path, 'rt') as f:
        d = json.load(f)
    for key, e in d['unique_tables'].items():
        if 'tables' not in e:
            continue
        board = Board.from_dict(e['board'])
        declarer = board.contract.declarer
        for table_a, table_b, ply, forced, band, estimated, propensity, cost_imps in plan_bench.forks_of(e):
            if STATE['bands'] is not None and band not in STATE['bands']:
                continue
            root, fork = e['tables'][table_a], e['tables'][table_b]
            act = root['actions'][ply]
            if not act.get('gen6') or root.get('status', 'ok') != 'ok' or fork.get('status', 'ok') != 'ok':
                continue
            game = Game(board)
            for x in root['actions'][:ply]:
                game.play(card(x['card']))
            o = game.observation()
            a, b = card(act['card']), card(forced)
            if a == b or b not in o.legal:
                continue
            seat = SEATS.index(act['seat'])
            sign = 1 if seat % 2 == declarer % 2 else -1
            row = dict(family=d['family'], table=key, table_a=table_a, table_b=table_b, pair=d.get('pair'), ply=ply, trick=ply // 4 + 1,
                       declaring=sign == 1, band=band, estimated=estimated, propensity=propensity, imps=cost_imps,
                       final=sign * (root['declarer_tricks'] - fork['declarer_tricks']), legal=len(o.legal), real_a=sign * root['declarer_tricks'])
            view = View(o)
            rng = np.random.default_rng([STATE['seed'], ply, int(d['family'][:8], 16)])
            worlds, weights, _ = six.layouts(o, view, six.source(o, view), rng)
            weights = np.asarray(weights, float)
            u = np.array([[x[a], x[b]] for x in (check.utilities(o, values) for values, _ in check.solve(six, o, worlds))])
            row['pimc'] = float(weights @ (u[:, 0] - u[:, 1]))
            row['layouts'] = len(worlds)
            truth = tuple(tuple(sorted(h)) for h in game.hands)
            (values, _), = check.solve(six, o, [truth])
            t = check.utilities(o, values)
            row['true_dd'], row['true_dd_a'] = float(t[a] - t[b]), float(t[a])
            k = STATE['worlds']
            index, share = systematic(weights, k, rng) if len(worlds) > k else (np.arange(len(worlds)), weights)
            started = time.perf_counter()
            r = np.array([[sign * played_out(o, board, worlds[i], x, f'{ply}-{n}') for x in (a, b)] for n, i in enumerate(index)], float)
            row['seconds_gen6'] = time.perf_counter() - started
            dd_k, roll_k = u[index, 0] - u[index, 1], r[:, 0] - r[:, 1]
            row['pimc_k'], row['gen6_k'] = float(share @ dd_k), float(share @ roll_k)
            row['gen6'] = row['pimc'] + row['gen6_k'] - row['pimc_k']
            row['var_gen6'] = float(share @ (roll_k - dd_k - share @ (roll_k - dd_k)) ** 2)
            row['neff_gen6'] = float(1 / (share ** 2).sum())
            row['sd_gen6'] = float(np.sqrt(share @ (roll_k - dd_k) ** 2))
            tr = [sign * played_out(o, board, truth, x, f'{ply}-true') for x in (a, b)]
            row['true_gen6'], row['true_a_gen6'] = float(tr[0] - tr[1]), float(tr[0])
            hidden = view.hidden[0]
            row['worlds'] = dict(share=[round(float(x), 5) for x in share], dd=u[index].tolist(), roll=r.tolist(), hidden_seat=hidden,
                                 hands=[format(sum(1 << c for c in worlds[i][hidden]), 'x') for i in index])
            rows.append(row)
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--episodes', type=Path, required=True)
    p.add_argument('--worlds', type=int, default=16)
    p.add_argument('--sim-samples', type=int, default=0, help='layouts the simulated seats search (0 = as Gen 6, 32)')
    p.add_argument('--from-trick', type=int, default=3)
    p.add_argument('--to-trick', type=int, default=6)
    p.add_argument('--bands', help='keep only these bands, e.g. 0,1')
    p.add_argument('--ties', action='store_true')
    p.add_argument('--pairs', type=int, default=10 ** 9)
    p.add_argument('--files', type=int, default=10 ** 9)
    p.add_argument('--skip-files', type=int, default=0)
    p.add_argument('--workers', type=int, default=2)
    p.add_argument('--seconds', type=float, default=1e9)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    files = sorted(a.episodes.glob('*.json.gz')) if a.episodes.is_dir() else [Path(x) for x in a.episodes.read_text().split()]
    files = files[a.skip_files:a.skip_files + a.files]
    bands = None if a.bands is None else tuple(int(x) for x in a.bands.split(','))
    rows, started, done = [], time.time(), 0

    def save():
        a.out.write_text(json.dumps(dict(settings=dict(sims=[dict(name='gen6', net=None, mode='gen6', repeats=1, tricks=0)], worlds=a.worlds,
                                                       sim_samples=a.sim_samples, from_trick=a.from_trick, to_trick=a.to_trick, ties=a.ties, bands=a.bands,
                                                       files=done, seed=a.seed, seconds=round(time.time() - started)), rows=rows)))

    with Pool(a.workers, initializer=start, initargs=(a.from_trick, a.to_trick, a.ties, a.seed, a.worlds, bands, a.sim_samples)) as pool:
        for got in pool.imap(pairs_of, files, chunksize=1):
            rows += got
            done += 1
            if done % 20 == 0:
                print(f'{done} files, {len(rows)} pairs, {round(time.time() - started)} s', flush=True)
                save()
            if len(rows) >= a.pairs or time.time() - started > a.seconds:
                pool.terminate()
                break
    save()
    print(json.dumps(dict(pairs=len(rows), files=done, seconds=round(time.time() - started))))


if __name__ == '__main__':
    main()
