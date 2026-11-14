#!/usr/bin/env python3
"""Honesty carried as a grid through the board, against its posterior mean (g9's question, G9-S5 / E9-4).

Gen 9 work in progress (sam, signals). Prediction evidence.

One honesty per opponent makes the signal likelihood of a board a product over its plays. With h
uncertain, the exact reading is the posterior average of that product,

    log L(x) = log sum over h of w(h) prod over plays of P_h(card | x)

which is not the product at the posterior mean. For cells std-80 and std-0 (relabelled defenders, as
scripts/gen9_reading_gain.py), the posterior over h on the grid 0, 0.1, ..., 1 comes from the card
statistics of the first N tables (flat prior, the reader's floor allowed for exactly), N = 0, 5, 10, 20.
On held-out tables both readers are scored at declarer's decisions: `point` (signal term at the
posterior mean) and `grid` (the mixture above), each with the class term at factor 1.

  python scripts/gen9_honesty_mixture.py EPISODES --source CAPSULE/recovery --out rows.jsonl
"""
import os
for _name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_name, '1')
import argparse
from concurrent.futures import ProcessPoolExecutor
import glob
import gzip
import json
from pathlib import Path
import sys
import zlib

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from bridge_harness import experience as xp  # noqa: E402
from bridge_harness.core import Board, Game  # noqa: E402
from bridge_harness.gen6 import View  # noqa: E402
from bridge_harness.gen7 import hidden_plays  # noqa: E402
from bridge_harness.gen9_play import SignalPlayer  # noqa: E402
from bridge_harness.signal_experience import card_stats  # noqa: E402
from bridge_harness.signals import SignalModel  # noqa: E402
from gen9_reading_gain import cell_model, gains, pool_layouts, relabel_consistent  # noqa: E402

GRID = tuple(round(.1 * k, 1) for k in range(11))
EPS = .05
STATE = {}


def posterior(stat):
    """Weights on GRID for honesty given a card.<key> count pooled over keys: flat prior, P(hit) = (1 - eps)(h + (1 - h)/n)
    + eps / s from the class-size labels."""
    cells = {}
    for label, v in ((stat or {}).get('n') or {}).items():
        parts = label.split('/')
        if len(parts) == 3:
            cells.setdefault((int(parts[1]), int(parts[2])), [0., 0.])[parts[0] == 'all'] += v
    grid = np.array(GRID)
    logp = np.zeros(len(grid))
    for (n, s), (hit, total) in cells.items():
        p = (1 - EPS) * (grid + (1 - grid) / n) + EPS / s
        logp += hit * np.log(p) + (total - hit) * np.log(np.maximum(1 - p, 1e-300))
    w = np.exp(logp - logp.max())
    return w / w.sum()


def table_files(episodes, count):
    jobs = []
    for path in sorted(glob.glob(str(Path(episodes) / '*.json.gz'))):
        with gzip.open(path, 'rt') as f:
            keys = sorted(json.load(f)['unique_tables'])
        jobs += [(path, k) for k in keys]
        if len(jobs) >= count:
            break
    return jobs[:count]


def load(path, key):
    with gzip.open(path, 'rt') as f:
        record = json.load(f)['unique_tables'][key]
    board = Board.from_dict(record['board'])
    main = [t for t in record['tables'] if t.get('depth', 0) == 0]
    if board.contract is None or not main or len(main[0]['actions']) < 8:
        return None, None
    return board, main[0]['actions']


def experience_stats(job):
    path, key, cell, seed = job
    board, actions = load(path, key)
    if board is None:
        return None
    got = relabel_consistent(board, actions, cell_model(cell), zlib.crc32(f'{Path(path).name}/{key}/{cell}/{seed}'.encode()))
    if got is None:
        return None
    pooled = {'kind': 'count', 'n': {}}
    for st in card_stats(board, got[0], cell_model(cell), 1 - board.contract.declarer % 2).values():
        pooled = xp.merge_stat(pooled, st)
    return pooled


def scored(job):
    path, key, cell, source, bot, pool, until, seed, priors = job
    if 'p' not in STATE:
        m = json.loads((Path(source) / 'manifest.json').read_text())
        STATE['p'] = SignalPlayer(dict(m['bots'][bot], gen9={}), source)
    p = STATE['p']
    board, actions = load(path, key)
    if board is None:
        return []
    bot_model = cell_model(cell)
    got = relabel_consistent(board, actions, bot_model, zlib.crc32(f'{Path(path).name}/{key}/{cell}/{seed}'.encode()))
    if got is None:
        return []
    plays = got[0]
    grid_models = {h: SignalModel(bot_model.descriptor, h, EPS) for h in GRID}
    point_models = {N: SignalModel(bot_model.descriptor, float(np.dot(w, GRID)), EPS) for N, w in priors.items()}
    rng = np.random.default_rng(zlib.crc32(f'{Path(path).name}/{key}/{seed}'.encode()))
    truth = tuple(tuple(sorted(h)) for h in board.hands)
    game = Game(board)
    rows = []
    for seat, x in plays:
        if game.done or len(game.history) // 4 + 1 >= until:
            break
        o = game.observation()
        if o.history and o.controller == board.contract.declarer and len(o.legal) > 1:
            view = View(o)
            hidden = hidden_plays(o, True)
            if len(view.hidden) == 2 and hidden:
                src, assign = pool_layouts(p, o, view, truth, pool, rng)
                class_part = np.zeros(len(assign))
                by_h = {h: np.zeros(len(assign)) for h in GRID}
                by_point = {N: np.zeros(len(assign)) for N in priors}
                for play in hidden:
                    for h, model in grid_models.items():
                        _, lk, ls = p.signal_row(o, view, assign, *play, model)
                        by_h[h] += ls
                    for N, model in point_models.items():
                        by_point[N] += p.signal_row(o, view, assign, *play, model)[2]
                    class_part += lk
                stack = np.stack([by_h[h] for h in GRID])                           # [grid, layouts]
                out = {}
                for N, w in priors.items():
                    mix = np.logaddexp.reduce(np.log(np.maximum(w, 1e-300))[:, None] + stack, axis=0)
                    out[f'point-N{N}'] = gains(class_part + by_point[N])
                    out[f'grid-N{N}'] = gains(class_part + mix)
                out['class'] = gains(class_part)
                rows.append(dict(episode=Path(path).name, table=key, cell=cell, trick=len(o.history) // 4 + 1, gains=out))
        game.play(x)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('episodes')
    ap.add_argument('--source', required=True)
    ap.add_argument('--bot', default='7s-32')
    ap.add_argument('--cells', default='std-80,std-0')
    ap.add_argument('--experience', type=int, default=20)
    ap.add_argument('--held-out', type=int, default=200, help='tables scored, after the first 100')
    ap.add_argument('--pool', type=int, default=256)
    ap.add_argument('--until', type=int, default=7)
    ap.add_argument('--seed', type=int, default=9)
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    tables = table_files(args.episodes, 100 + args.held_out)
    summary = {}
    with ProcessPoolExecutor(args.workers) as pool:
        for cell in args.cells.split(','):
            stats = list(pool.map(experience_stats, [(p_, k, cell, args.seed) for p_, k in tables[:args.experience]]))
            priors = {}
            for N in (0, 5, 10, 20):
                pooled = {'kind': 'count', 'n': {}}
                for st in [s for s in stats[:N] if s]:
                    pooled = xp.merge_stat(pooled, st)
                priors[N] = posterior(pooled)
            summary[cell] = {N: dict(mean=round(float(np.dot(w, GRID)), 3), weights=[round(float(v), 4) for v in w]) for N, w in priors.items()}
            print(cell, {N: v['mean'] for N, v in summary[cell].items()}, flush=True)
            jobs = [(p_, k, cell, str(Path(args.source).resolve()), args.bot, args.pool, args.until, args.seed, priors) for p_, k in tables[100:]]
            with open(args.out, 'a') as out:
                for rows in pool.map(scored, jobs, chunksize=1):
                    for r in rows:
                        out.write(json.dumps(r) + '\n')
    Path(args.out).with_suffix('.priors.json').write_text(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
