#!/usr/bin/env python3
"""How much does the net's reading of the play say about the hidden hands before the deal list?

Work in progress (Gen 8 prototype). For every early decision in recorded tables (after the opening
lead, two hidden hands, before trick `--until`), a pool of layouts is drawn by the hand-fit
scorer's class weights exactly as Gen7Player.early_layouts draws it, and the play so far is
scored by the policy net in each pool layout and in the true layout. The gain at exponent p is

    p * fit(true layout) - log mean over the pool of exp(p * fit(layout))

the log of how much the true layout's weight rises against the auction-only weights. Positive
on average means the reading moves weight toward the truth; the exponent with the largest mean
gain is the calibrated one. Standard errors are clustered by table.

  python scripts/gen8_play_info.py --source CAPSULE/recovery --bots configs/gen8-proto-bots.json --bot 8s-32 RUN/episodes
"""
import os
for _name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_name, '1')
import argparse
import glob
import gzip
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from bridge_harness.core import Board, Game, card  # noqa: E402
from bridge_harness.gen6 import Classes, View, spaced  # noqa: E402
from bridge_harness.gen7 import floored, hidden_plays, player  # noqa: E402
from gen8_match import build_manifest  # noqa: E402

POWERS = (0.25, 0.5, 0.75, 1.0, 1.5)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('episodes')
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--bots', required=True)
    ap.add_argument('--bot', required=True, help='whose net and scorer read the play')
    ap.add_argument('--pool', type=int, default=512)
    ap.add_argument('--until', type=int, default=7, help='first trick not scored')
    ap.add_argument('--tables', type=int, default=10 ** 9)
    ap.add_argument('--out')
    ap.add_argument('--mover', help="only decisions made by this role: 'candidate' or 'opponent'")
    args = ap.parse_args()
    m = build_manifest(args.source.resolve(), args.bots, f'{args.bot}~6-32', 1)
    p = player(m['bots'][args.bot], str(args.source.resolve()))
    rng = np.random.default_rng(0)
    rows, tables = [], 0
    for path in sorted(glob.glob(str(Path(args.episodes) / '*.json.gz'))):
        with gzip.open(path, 'rt') as f:
            episode = json.load(f)
        for record in episode['unique_tables'].values():
            if tables >= args.tables or not record['tables'][0]['actions']:
                continue
            tables += 1
            game = Game(Board.from_dict(record['board']))
            for a in record['tables'][0]['actions']:
                o = game.observation()
                trick = len(o.history) // 4 + 1
                view = View(o) if o.history and trick < args.until else None
                plays = hidden_plays(o, True) if view is not None else []
                if view is not None and len(view.hidden) == 2 and plays and len(o.legal) > 1:
                    source = p.source(o, view)
                    if source == 'list' and args.until > 7:                   # the deal list: every card-fit layout, scorer-weighted
                        every = view.every()
                        logw = p.layout_log_weights(o, view, every)
                        if len(every) > args.pool:
                            pick = rng.choice(len(every), args.pool, p=np.exp(logw - logw.max()) / np.exp(logw - logw.max()).sum())
                            every = every[pick]
                        else:                                                 # the whole list: weight it instead of drawing from it
                            keep = rng.choice(len(every), args.pool, p=np.exp(logw - logw.max()) / np.exp(logw - logw.max()).sum())
                            every = every[keep]
                        owner = np.zeros(52, np.int8)
                        truth = tuple(tuple(sorted(h)) for h in game.hands)
                        owner[list(truth[view.hidden[1]])] = 1
                        owner[list(truth[view.hidden[0]])] = 0
                        assign = np.concatenate([every, owner[view.unseen][None].astype(every.dtype)])
                        logp, options = p.play_log_probabilities(o, view, assign, plays)
                        each = floored(logp, options, p.g7.play_floor)
                        theirs = np.array([chooser % 2 != o.controller % 2 for _, _, chooser in plays])

                        def gain(rows_used):
                            fit = each[rows_used].sum(axis=0)
                            return [float(q * fit[-1] - (np.logaddexp.reduce(q * fit[:-1]) - np.log(len(fit) - 1))) for q in POWERS]
                        rows.append(dict(table=tables, trick=trick, plays=len(plays), declaring=bool(o.controller % 2 == o.contract.declarer % 2),
                                         gains=gain(np.ones(len(plays), bool)), theirs=gain(theirs), partner=gain(~theirs), mover=a['player']))
                    if source in ('scorer', 'lead_net'):
                        classes = Classes(view)
                        logw = classes.logmult + p.type_log_weights(o, view, classes.length, classes.hon, source)
                        worlds = classes.worlds(spaced(logw, args.pool, rng.random()), rng)
                        worlds.append(tuple(tuple(sorted(h)) for h in game.hands))               # the true layout, last
                        owner = np.zeros(52, np.int8)
                        assign = np.empty((len(worlds), len(view.unseen)), np.int8)
                        for k, world in enumerate(worlds):
                            owner[list(world[view.hidden[1]])] = 1
                            owner[list(world[view.hidden[0]])] = 0
                            assign[k] = owner[view.unseen]
                        logp, options = p.play_log_probabilities(o, view, assign, plays)
                        each = floored(logp, options, p.g7.play_floor)                      # [plays, layouts]
                        theirs = np.array([chooser % 2 != o.controller % 2 for _, _, chooser in plays])

                        def gain(rows_used):
                            fit = each[rows_used].sum(axis=0)
                            return [float(q * fit[-1] - (np.logaddexp.reduce(q * fit[:-1]) - np.log(len(fit) - 1))) for q in POWERS]
                        declaring = o.controller % 2 == o.contract.declarer % 2
                        rows.append(dict(table=tables, trick=trick, plays=len(plays), declaring=bool(declaring), gains=gain(np.ones(len(plays), bool)),
                                         theirs=gain(theirs), partner=gain(~theirs), mover=a['player']))
                game.play(card(a['card']))
    p.close()
    table = np.array([r['table'] for r in rows])
    if args.mover:
        rows = [r for r in rows if r['mover'] == args.mover]
        table = np.array([r['table'] for r in rows])
    gains = np.array([r['gains'] for r in rows])
    by_side = dict(theirs=np.array([r['theirs'] for r in rows]), partner=np.array([r['partner'] for r in rows]))
    trick = np.array([r['trick'] for r in rows])
    side = np.array([r['declaring'] for r in rows])

    def line(mask, values=None):
        values = gains if values is None else values
        ids = np.unique(table[mask])
        per = np.array([values[mask & (table == t)].sum(axis=0) for t in ids])
        n = np.array([(mask & (table == t)).sum() for t in ids])
        mean = per.sum(axis=0) / n.sum()
        se = np.sqrt(len(ids) / max(len(ids) - 1, 1) * ((per - mean * n[:, None]) ** 2).sum(axis=0)) / n.sum()
        return int(mask.sum()), mean, se

    print(f'{len(rows)} early decisions in {tables} tables; pool {args.pool}; floor {p.g7.play_floor}')
    print('gain in nats of the true layout over auction-only weights, by exponent ' + ' '.join(f'{q:>13}' for q in POWERS))
    report = {}
    groups = [('all', np.ones(len(rows), bool)), ('declarer', side), ('defender', ~side)] + [(f'trick {t}', trick == t) for t in sorted(set(trick))]
    for name, mask in groups:
        if mask.sum() < 2:
            continue
        n, mean, se = line(mask)
        report[name] = dict(decisions=n, mean=[round(float(x), 4) for x in mean], se=[round(float(x), 4) for x in se])
        print(f'{name:>10} {n:6d} ' + ' '.join(f'{a:+.3f}+-{b:.3f}' for a, b in zip(mean, se)))
    for name, values in (("opponents' plays only", by_side['theirs']), ("partner's plays only (defenders)", by_side['partner'])):
        mask = ~side if name.startswith('partner') else np.ones(len(rows), bool)
        if mask.sum() > 1:
            n, mean, se = line(mask, values)
            report[name] = dict(decisions=n, mean=[round(float(x), 4) for x in mean], se=[round(float(x), 4) for x in se])
            print(f'{name}: {n} ' + ' '.join(f'{a:+.3f}+-{b:.3f}' for a, b in zip(mean, se)))
    if args.out:
        Path(args.out).write_text(json.dumps(dict(powers=POWERS, groups=report, tables=tables), indent=1))


if __name__ == '__main__':
    main()
