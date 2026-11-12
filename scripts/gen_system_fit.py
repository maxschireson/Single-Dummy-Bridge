#!/usr/bin/env python3
"""Training data for a system-aware hand-fit scorer: random deals bid at mixed tables.

Work in progress (Gen 8 system layer, not the final form, used by no arena bot): docs/gen8_systems.md.

    python scripts/gen_system_fit.py OUT.npz --seed 3000 --deals 20000 --systems house-gen6,house-gen5
    python scripts/gen_system_fit.py OUT.npz --seed 3000 --deals 20000 --tables house-gen6:house-gen5,house-gen5:house-gen6:2

--systems plays every ordered pairing of the listed systems, each against itself too, with
equal shares of the deals. --tables lists North-South:East-West pairings, each with an
optional weight. Systems are looked up in the registry (configs/systems). Each system's
generator is built and its identity checked against the pinned sha256 before any auction is
labelled with that system.
"""
import argparse
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness import system_fit as F  # noqa: E402
from bridge_harness.system_bidders import make_bidder  # noqa: E402
from bridge_harness.systems import SystemRegistry  # noqa: E402


def tables_from(args):
    if bool(args.systems) == bool(args.tables):
        raise SystemExit('give --systems or --tables')
    if args.systems:
        ids = args.systems.split(',')
        return [(a, b, 1.0) for a in ids for b in ids]
    out = []
    for item in args.tables.split(','):
        ns, ew, *weight = item.split(':')
        out.append((ns, ew, float(weight[0]) if weight else 1.0))
    return out


def shares(weights, total):
    """Whole deals per table in proportion to the weights (largest remainders)."""
    exact = np.array(weights) / np.sum(weights) * total
    n = np.floor(exact).astype(int)
    n[np.argsort(-(exact - n))[:total - n.sum()]] += 1
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('out')
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--deals', type=int, required=True, help='total over all tables')
    ap.add_argument('--systems')
    ap.add_argument('--tables')
    ap.add_argument('--registry', default=str(ROOT / 'configs' / 'systems'))
    ap.add_argument('--root', default=str(ROOT), help='folder that generator paths are relative to')
    ap.add_argument('--external-root', help='folder that holds external generators (for example a BEN install)')
    args = ap.parse_args()
    registry = SystemRegistry.load(args.registry)
    tables = tables_from(args)
    bidders = {}
    for s in sorted({s for ns, ew, _ in tables for s in (ns, ew)}):
        bidders[s] = make_bidder(registry[s].generator(), args.root, args.external_root)
        registry.require_generator(s, bidders[s].sha256)
    parts = []
    for i, ((ns, ew, _), n) in enumerate(zip(tables, shares([w for _, _, w in tables], args.deals))):
        if not n:
            continue
        t0 = time.time()
        q = F.generate(np.random.default_rng([args.seed, i]), (bidders[ns], bidders[ew]), int(n))
        ids = [ns] if ns == ew else [ns, ew]
        q.update(systems=np.array(ids), generators=np.array([bidders[s].sha256 for s in ids]),
                 d_sys=np.tile(np.array([0, len(ids) - 1]), (len(q['d_dealer']), 1)))
        parts.append(q)
        lab, kind = q['label'], q['kind']
        print(f'{ns} (NS) vs {ew} (EW): {n} deals in {time.time() - t0:.0f}s; positive share: random hands {lab[kind == 1].mean():.3f}, '
              f'near hands {lab[kind == 2].mean():.3f}', flush=True)
    data = F.merge(parts)
    np.savez(args.out, **data)
    print(f'{args.out}: {len(data["d_dealer"])} deals, {len(data["label"])} examples, systems {[str(s) for s in data["systems"]]}')


if __name__ == '__main__':
    main()
