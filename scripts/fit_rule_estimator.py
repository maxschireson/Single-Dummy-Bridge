"""Fit the rule bidder's trick estimate to double-dummy results.

The rule bidder (bridge_harness/rule_bidder.py) places contracts by point count unless its settings name a
trick estimate: a small network from the bidder's own hand and what the other three seats have shown
(rule_bidder.features) to the tricks each side would take as declarer in each strain. This script makes one.

  dump   bid random deals with the rule system against the house bidder (each way round) and against itself,
         and at every turn of a rule seat record what the estimate will see, with the deal it came from
  fit    train the network on those records against the deals' double-dummy tables, and write it as JSON

    python scripts/fit_rule_estimator.py dump --source CAPSULE/recovery --seeds 401,402 --deals 4000 \\
        --settings configs/rule-systems/precision.json --cache DDCACHE --workers 8 --out states.npz
    python scripts/fit_rule_estimator.py fit --states states.npz --cache DDCACHE --out estimate.json

The deals and the tables are those of scripts/tune_rule_bidder.py (a function of seed and index; tables cached
as dd-<seed>.npz). An estimate describes the hands behind the calls of the bidder that made the records, so
after the bidder's judgement changes (it starts using an estimate, or a new one) the records are made again
with it and the estimate refitted: `--estimate` on dump names the one the bidder uses while it bids.
"""
import argparse
import importlib.util
import json
from dataclasses import asdict
from multiprocessing import Pool
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('tune_rule_bidder', ROOT / 'scripts/tune_rule_bidder.py')
T = importlib.util.module_from_spec(spec)
sys.modules['tune_rule_bidder'] = T
spec.loader.exec_module(T)

from bridge_harness import rule_bidder as R  # noqa: E402

ROW = {0: 3, 1: 2, 2: 1, 3: 0, 4: 4}        # the double-dummy table's row of a strain (clubs, diamonds, hearts, spades, no trump)
STATE = {}


def start(source, settings):
    STATE.update(house=T.House(source), settings=settings)


def dump_chunk(job):
    seed, first, count = job
    rows, meta = [], []
    cand, same = R.RuleSystemBidder(STATE['settings']), R.RuleSystemBidder(STATE['settings'], opponents='same')
    house = STATE['house']
    for i in range(first, first + count):
        board = T.deal(seed, i)
        for sides in ((cand, house), (house, cand), (same, same)):
            def tap(h, st, seat):
                rows.append(R.features(h, st, seat))
                meta.append((seed, i, seat, len(st.calls)))
            for b in set(sides):
                if b is not house:
                    b.tap = tap
            T.auction(board, (seed, i), sides)
    for b in (cand, same):
        b.tap = None
    return np.asarray(rows, np.float32), np.asarray(meta, np.int32)


def dump(args):
    settings = json.loads(Path(args.settings).read_text())['settings'] if args.settings else asdict(R.Settings())
    if args.estimate is not None:
        settings = dict(settings, estimate=args.estimate)
    jobs = [(seed, first, min(250, args.deals - first)) for seed in args.seeds for first in range(0, args.deals, 250)]
    t = time.time()
    with Pool(args.workers, initializer=start, initargs=(args.source, settings)) as pool:
        parts = pool.map(dump_chunk, jobs, chunksize=1)
    x, meta = np.concatenate([p[0] for p in parts]), np.concatenate([p[1] for p in parts])
    np.savez_compressed(args.out, x=x, meta=meta, settings=json.dumps(settings), rules=R.RULES)
    print(f'{len(x)} states from {len(args.seeds) * args.deals} deals in {time.time() - t:.0f}s -> {args.out}', flush=True)


def targets(meta, cache):
    """For each record: our side's and their side's tricks as declarer in each strain (the mean of the side's two seats)."""
    y = np.empty((len(meta), 10), np.float32)
    for seed in np.unique(meta[:, 0]):
        tables = np.load(Path(cache) / f'dd-{seed}.npz')['t'].astype(np.float32)
        rows = np.flatnonzero(meta[:, 0] == seed)
        t = tables[meta[rows, 1]]                        # [record, table row, declarer]
        side = meta[rows, 2] % 2
        for strain in range(5):
            ns, ew = t[:, ROW[strain], 0::2].mean(1), t[:, ROW[strain], 1::2].mean(1)
            y[rows, strain] = np.where(side == 0, ns, ew)
            y[rows, 5 + strain] = np.where(side == 0, ew, ns)
    return y


def fit(args):
    data = [np.load(f, allow_pickle=False) for f in args.states]
    x, meta = np.concatenate([d['x'] for d in data]), np.concatenate([d['meta'] for d in data])
    y = targets(meta, args.cache)
    rng = np.random.default_rng(args.seed)
    deals = np.unique(meta[:, :2], axis=0)
    held = {tuple(d) for d in deals[rng.permutation(len(deals))[:max(1, len(deals) // 10)]]}
    val = np.fromiter(((int(a), int(b)) in held for a, b in meta[:, :2]), bool, len(meta))
    xt, yt, xv, yv = x[~val], y[~val], x[val], y[val]
    sizes = [x.shape[1]] + [args.width] * args.depth + [10]
    layers = [(rng.normal(0, np.sqrt(2. / a), (a, b)).astype(np.float32), np.zeros(b, np.float32)) for a, b in zip(sizes[:-1], sizes[1:])]
    layers[-1][1][:] = yt.mean(0)
    moments = [[np.zeros_like(w), np.zeros_like(w), np.zeros_like(b), np.zeros_like(b)] for w, b in layers]

    def forward(a):
        acts = [a]
        for k, (w, b) in enumerate(layers):
            a = a @ w + b
            if k < len(layers) - 1:
                a = np.maximum(a, 0.)
            acts.append(a)
        return acts

    steps, t0, best, best_layers = int(args.epochs * len(xt) / args.batch), time.time(), 1e9, None
    for step in range(1, steps + 1):
        idx = rng.integers(0, len(xt), args.batch)
        acts = forward(xt[idx])
        grad = 2. * (acts[-1] - yt[idx]) / args.batch
        lr = args.lr * 0.5 * (1 + np.cos(np.pi * step / steps))
        for k in range(len(layers) - 1, -1, -1):
            w, b = layers[k]
            gw, gb = acts[k].T @ grad, grad.sum(0)
            if k:
                grad = (grad @ w.T) * (acts[k] > 0)
            for j, (param, g) in enumerate(((w, gw), (b, gb))):
                m, v = moments[k][2 * j], moments[k][2 * j + 1]
                m *= 0.9; m += 0.1 * g
                v *= 0.999; v += 0.001 * g * g
                param -= lr * (m / (1 - 0.9 ** step)) / (np.sqrt(v / (1 - 0.999 ** step)) + 1e-8)
        if step % max(1, steps // 10) == 0 or step == steps:
            err = forward(xv)[-1] - yv
            rmse = float(np.sqrt((err ** 2).mean()))
            if rmse < best:
                best, best_layers = rmse, [(w.copy(), b.copy()) for w, b in layers]
            print(f'  step {step}/{steps} ({time.time() - t0:.0f}s): held-out error {rmse:.3f} tricks', flush=True)
    layers[:] = best_layers
    err = forward(xv)[-1] - yv
    sigma = np.sqrt((err ** 2).mean(0))
    # for comparison: the error of a straight line through the side's combined minimum points, per strain
    report = dict(states=int(len(x)), deals=int(len(deals)), held_out_deals=len(held), width=args.width, depth=args.depth,
                  rmse=round(float(np.sqrt((err ** 2).mean())), 4), sigma=[round(float(s), 3) for s in sigma],
                  spread_of_tricks=[round(float(s), 3) for s in yv.std(0)], rules=str(data[0]['rules']),
                  settings=json.loads(str(data[0]['settings'])))
    out = dict(note='Trick estimate for bridge_harness/rule_bidder.py, fitted by scripts/fit_rule_estimator.py. Outputs: our tricks as '
                    'declarer in clubs, diamonds, hearts, spades, no trump, then theirs. sigma: held-out error of each.',
               report=report, sigma=report['sigma'],
               layers=[[np.round(w, 5).tolist(), np.round(b, 5).tolist()] for w, b in layers])
    Path(args.out).write_text(json.dumps(out) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'settings'}))
    print(f'wrote {args.out}')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='mode', required=True)
    d = sub.add_parser('dump')
    d.add_argument('--source', required=True, help='a run capsule (for the house bidder)')
    d.add_argument('--seeds', type=lambda s: [int(v) for v in s.split(',')], required=True)
    d.add_argument('--deals', type=int, default=4000, help='deals of each seed')
    d.add_argument('--settings', help='JSON {"settings": {...}}; default: the built-in settings')
    d.add_argument('--estimate', help='the trick estimate the bidder uses while it bids ("" for none; default: as the settings say)')
    d.add_argument('--workers', type=int, default=4)
    d.add_argument('--out', required=True)
    f = sub.add_parser('fit')
    f.add_argument('--states', nargs='+', required=True)
    f.add_argument('--cache', required=True, help='folder of dd-<seed>.npz tables')
    f.add_argument('--width', type=int, default=128)
    f.add_argument('--depth', type=int, default=2)
    f.add_argument('--epochs', type=float, default=12)
    f.add_argument('--batch', type=int, default=512)
    f.add_argument('--lr', type=float, default=2e-3)
    f.add_argument('--seed', type=int, default=1)
    f.add_argument('--out', required=True)
    args = p.parse_args()
    dump(args) if args.mode == 'dump' else fit(args)


if __name__ == '__main__':
    main()
