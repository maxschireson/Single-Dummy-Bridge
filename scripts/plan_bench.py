#!/usr/bin/env python3
"""Score honest playouts on fork pairs: does playing the hand out say which card did better?

  python scripts/plan_bench.py --episodes DIR_OR_LIST --nets v4=PATH,v41=PATH --sims "v41:top;v41:map;v4:top" \
        [--from-trick 3] [--to-trick 6] [--ties] [--pairs 2000] [--workers 2] [--out rows.json]

In a fork pair A is the card Gen 6 played and B a card the collector forced at the same decision and
played out with the same bots, so the realized cost of B is known (scripts/gen7_bench.py has the
full description). For each pair the position is rebuilt, Gen 6's own layouts are drawn again, and
A and B are valued on those layouts by

  pimc        plain double dummy (Gen 6 again, with a fresh draw)
  <sim>       playing the hand out to trick 13 with a simulated player at every seat
              (bridge_harness/plan_rollout.py); NET:MODE[:repeats[:tricks]] names the net and how it picks;
              with `tricks` the playout stops after that many tricks and is solved double dummy from there

and, on the real deal alone (which no player could use; it measures the simulator, not a decision):

  true_dd     double dummy on the real deal
  true_<sim>  the playout on the real deal

Every figure is A minus B in the decider's tricks, so a negative value prefers B. `final` is what B
really cost. Rows go to --out; scripts/plan_report.py reads them.
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
from bridge_harness.core import SEATS, Board, Game, card
from bridge_harness.gen6 import View
from bridge_harness.gen7 import player
from bridge_harness.gen7_net import PolicyNet
from bridge_harness.plan_rollout import Believer, NetPlayer, Public, card_values
import gen7_check as check

STATE = {}


def parse_sims(text):
    out = []
    for part in filter(None, text.split(';')):
        bits = part.split(':')
        out.append(dict(name=part.replace(':', '_'), net=bits[0], mode=bits[1], repeats=int(bits[2]) if len(bits) > 2 else 1,
                        tricks=int(bits[3]) if len(bits) > 3 else 0))
    return out


def seat_player(net, dds, mode, seed):
    """top, draw, blend: the net's card. map, bdraw: the solver's card for the seat's believed layout (most likely,
    or drawn); a number after either (map3) is how many believed layouts are solved."""
    for name, belief in (('map', 'map'), ('bdraw', 'draw')):
        if mode.startswith(name):
            return Believer(net, dds, belief, layouts=int(mode[len(name):] or 1), seed=seed)
    return NetPlayer(net, mode, seed=seed)


def start(nets, sims, from_trick, to_trick, ties, seed):
    os.environ['BRIDGE_DDS_CACHE'] = ''
    six = player(check.spec('gen6'), ROOT)
    STATE.update(six=six, nets={k: PolicyNet(Path(v).resolve(), six.scorer) for k, v in nets.items()}, sims=sims,
                 from_trick=from_trick, to_trick=to_trick, ties=ties, seed=seed)


def forks_of(e):
    """(table A was played at, table B was played at, ply, card B, band, estimated gap, sampling probability, IMPs B cost)"""
    ok = lambda ply: ply > 0 and STATE['from_trick'] <= ply // 4 + 1 <= STATE['to_trick']
    forks = [(0, g['fork_table'], g['ply'], g['forced_card'], g['band'], g['estimated_gap'], g['propensity'], g.get('realized_cost_imps'))
             for g in e.get('gap_forks') or [] if ok(g['ply'])]
    if STATE['ties']:
        forks += [(x['candidate_table'], x['reference_table'], x['ply'], x['reference_card'], -1, 0., x['audit_probability'], x.get('gain_imps'))
                  for x in e.get('audits') or [] if not x['identical_action'] and ok(x['ply'])
                  and not (e['tables'][x['candidate_table']]['actions'][x['ply']].get('gen7_tree') or {}).get('audit_reference')]
    return sorted(forks, key=lambda g: (g[2], g[0], g[1]))


def pairs_of(path):
    six, rows = STATE['six'], []
    with gzip.open(path, 'rt') as f:
        d = json.load(f)
    for key, e in d['unique_tables'].items():
        if 'tables' not in e:
            continue
        forks = forks_of(e)
        if not forks:
            continue
        board = Board.from_dict(e['board'])
        declarer = board.contract.declarer
        publics = {}
        for table_a, table_b, ply, forced, band, estimated, propensity, cost_imps in forks:
            root, fork = e['tables'][table_a], e['tables'][table_b]
            act = root['actions'][ply]
            if not act.get('gen6') or len(root['actions']) <= ply or root.get('status', 'ok') != 'ok' or fork.get('status', 'ok') != 'ok':
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
                       final=sign * (root['declarer_tricks'] - fork['declarer_tricks']), legal=len(o.legal))
            view = View(o)
            rng = np.random.default_rng([STATE['seed'], ply, int(d['family'][:8], 16)])
            started = time.perf_counter()
            worlds, weights, _ = six.layouts(o, view, six.source(o, view), rng)
            weights = np.asarray(weights, float)
            u = np.array([[x[a], x[b]] for x in (check.utilities(o, values) for values, _ in check.solve(six, o, worlds))])
            row['pimc'] = float(weights @ (u[:, 0] - u[:, 1]))
            row['layouts'] = len(worlds)
            row['neff'] = float(1 / (weights ** 2).sum())
            row['seconds_pimc'] = time.perf_counter() - started
            truth = tuple(tuple(sorted(h)) for h in game.hands)
            (values, _), = check.solve(six, o, [truth])
            t = check.utilities(o, values)
            row['true_dd'] = float(t[a] - t[b])
            row['true_dd_a'] = float(t[a])
            row['true_in_layouts'] = truth in set(worlds)
            for sim in STATE['sims']:
                net = STATE['nets'][sim['net']]
                if sim['net'] not in publics:
                    publics[sim['net']] = Public(net, o)
                who = seat_player(net, six.dds, sim['mode'], [STATE['seed'], ply, int(d['family'][8:16], 16)])
                started = time.perf_counter()
                v = card_values(o, worlds, [a, b], who, publics[sim['net']], sim['repeats'], sim['tricks'], six.dds)
                row[sim['name']] = float(weights @ (v[:, 0] - v[:, 1]))
                change = (v[:, 0] - v[:, 1]) - (u[:, 0] - u[:, 1])
                row['sd_' + sim['name']] = float(np.sqrt(weights @ change ** 2))
                row['var_' + sim['name']] = float(weights @ (change - weights @ change) ** 2)
                tv = card_values(o, [truth], [a, b], who, publics[sim['net']], max(sim['repeats'], 1), sim['tricks'], six.dds)
                row['true_' + sim['name']] = float(tv[0, 0] - tv[0, 1])
                row['true_a_' + sim['name']] = float(tv[0, 0])
                row['seconds_' + sim['name']] = time.perf_counter() - started
            row['real_a'] = sign * root['declarer_tricks']
            rows.append(row)
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--episodes', type=Path, required=True, help='a folder of *.json.gz, or a text file listing them')
    p.add_argument('--nets', required=True, help='name=path,name=path')
    p.add_argument('--sims', required=True, help='NET:MODE[:repeats[:tricks]];...  modes: top, blend, draw (the net plays); map, bdraw, map3 (the solver plays the believed layout)')
    p.add_argument('--from-trick', type=int, default=3)
    p.add_argument('--to-trick', type=int, default=6)
    p.add_argument('--ties', action='store_true')
    p.add_argument('--pairs', type=int, default=10 ** 9)
    p.add_argument('--files', type=int, default=10 ** 9)
    p.add_argument('--skip-files', type=int, default=0)
    p.add_argument('--workers', type=int, default=2)
    p.add_argument('--seconds', type=float, default=1e9)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    nets = dict(item.split('=') for item in a.nets.split(','))
    sims = parse_sims(a.sims)
    files = sorted(a.episodes.glob('*.json.gz')) if a.episodes.is_dir() else [Path(x) for x in a.episodes.read_text().split()]
    files = files[a.skip_files:a.skip_files + a.files]
    rows, started, done = [], time.time(), 0
    with Pool(a.workers, initializer=start, initargs=(nets, sims, a.from_trick, a.to_trick, a.ties, a.seed)) as pool:
        for got in pool.imap(pairs_of, files, chunksize=2):
            rows += got
            done += 1
            if done % 50 == 0:
                print(f'{done} files, {len(rows)} pairs, {round(time.time() - started)} s', flush=True)
            if len(rows) >= a.pairs or time.time() - started > a.seconds:
                pool.terminate()
                break
    a.out.write_text(json.dumps(dict(settings=dict(nets=nets, sims=sims, from_trick=a.from_trick, to_trick=a.to_trick, ties=a.ties, files=done,
                                                   seed=a.seed, seconds=round(time.time() - started)), rows=rows)))
    print(json.dumps(dict(pairs=len(rows), files=done, seconds=round(time.time() - started))))


if __name__ == '__main__':
    main()
