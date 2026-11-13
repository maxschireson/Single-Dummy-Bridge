#!/usr/bin/env python3
"""Train or extend a system-aware hand-fit scorer (bridge_harness/system_fit.py).

Work in progress (Gen 8 system layer, not the final form, used by no arena bot): docs/gen8_systems.md.

    # every system in the data, starting from a pre-system scorer: its call table becomes the
    # shared table, so before training every system reads exactly as that scorer does
    python scripts/train_system_scorer.py OUT.npz --minutes 20 --val VAL.npz --train A.npz B.npz \
        --init models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz

    # add one system to a trained file; every other array is left exactly as it is
    python scripts/train_system_scorer.py OUT.npz --minutes 10 --val VAL.npz --train NEW.npz \
        --init OLD.npz --systems new-system --only new-system

Without --systems the model gets every system found in the training data. Data labelled with
a system the model does not have trains the shared ('unknown') reading. Every system in the
data must be pinned to its generator in the registry.
"""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness import system_fit as F  # noqa: E402
from bridge_harness.system_bidders import file_sha256  # noqa: E402
from bridge_harness.systems import SystemRegistry  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('out')
    ap.add_argument('--train', nargs='+', required=True)
    ap.add_argument('--val', required=True)
    ap.add_argument('--minutes', type=float)
    ap.add_argument('--steps', type=int)
    ap.add_argument('--init', help='a system-aware file to continue, or a pre-system FitScorer file')
    ap.add_argument('--systems', help='comma-separated systems the model should have (default: all in the training data)')
    ap.add_argument('--only', help='comma-separated systems whose own tables are trained; everything else is frozen')
    ap.add_argument('--views', default='0.5,0.25,0.25', help='P(declared), P(both hidden), P(each side hidden with 1/2)')
    ap.add_argument('--widths', default='768,512,256')
    ap.add_argument('--lr', default='2e-3,1e-4', help='first and last learning rate (cosine between them); lower both to fine-tune')
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--registry', default=str(ROOT / 'configs' / 'systems'))
    ap.add_argument('--report', help='write the per-table validation results here as JSON')
    args = ap.parse_args()
    registry = SystemRegistry.load(args.registry)
    data, val = F.load_data(args.train), F.load_data([args.val])
    for d in (data, val):
        for system, sha in zip(d['systems'], d['generators']):
            registry.require_generator(str(system), str(sha))
    wanted = args.systems.split(',') if args.systems else [str(s) for s in data['systems']]
    for s in wanted:
        registry.check_declared(s)
    if args.init:
        model = F.Model.load(args.init)
    else:
        model = F.Model.new(seed=args.seed, widths=tuple(int(w) for w in args.widths.split(',')))
    for s in wanted:
        if s not in model.sys_ids:
            model.add_system(s)
    only = args.only.split(',') if args.only else None
    print(f'{len(data["label"])} examples from {len(data["d_dealer"])} deals; model systems {model.sys_ids[1:]}'
          + (f'; training only {only}' if only else ''), flush=True)
    t0 = time.time()
    run = F.train(model, data, val, minutes=args.minutes, steps=args.steps, views=tuple(float(x) for x in args.views.split(',')),
                    only=only, seed=args.seed, lr=tuple(float(x) for x in args.lr.split(',')))
    rows = F.by_table(model, val)
    meta = dict(run, minutes=round((time.time() - t0) / 60, 2), views=args.views, lr=args.lr, only=only, seed=args.seed,
                init=dict(file=args.init, sha256=file_sha256(args.init)) if args.init else None,
                generators={str(s): str(g) for s, g in zip(data['systems'], data['generators'])},
                train_deals=int(len(data['d_dealer'])), validation=rows)
    out = args.out if args.out.endswith('.npz') else args.out + '.npz'
    model.save(out, meta)
    print(f'{out}: sha256 {file_sha256(out)}; kept the state at step {run["best_step"]} of {run["steps"]}')
    print('validation loss by table (lower is better); "wrong" declares another system on purpose:')
    for r in rows:
        print(f'  {r["ns"]:>24} vs {r["ew"]:<24} ' + '  '.join(f'{m} {r[m]["loss"]:.4f}' for m in ('declared', 'unknown', 'wrong') if m in r))
    if args.report:
        Path(args.report).write_text(json.dumps(meta, indent=2) + '\n')


if __name__ == '__main__':
    main()
