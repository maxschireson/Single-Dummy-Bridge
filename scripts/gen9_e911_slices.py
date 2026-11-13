#!/usr/bin/env python3
"""E9-11 on the reading bench: readings paired against a base by slice, in tricks a board and nats.

  python scripts/gen9_e911_slices.py --out POOLS --pair rpl:proto --pair rplonly: [--json FILE]

POOLS is p41's pools folder with fit-<name> files (gen9_reading_bench.py replay) and rpl files (gen9_replay_terms.py);
`A:B` pairs reading A with reading B, and an empty B is no reading. Only the fit files the pairs name are read.

Every reading is scored as p41's report scores it (gen8_reading_bench.score at exponent 1: 32 layouts resampled
before the deal list, up to 256 from it on, the prototype's early_min_effective). "A board" is p41's unit, one table
(four seats): a slice's figure is its decisions' share of the per-board total, so slices that split the decisions add
up to the whole. Standard errors by deal.

Slices: all; declarer or defender deciding; before the deal list or from it on; both hidden seats played by house bots
(p41's hidden_house); the hidden seats' calls all the house bidder's own (rpl's house flags) or not; the most calls
other than pass made by one hidden seat (0, 1, 2 or more).
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import gen8_reading_bench as bench  # noqa: E402

SEATS = 'NESW'


def calls_by_seat(board):
    dealer = SEATS.index(board['dealer'])
    n = [0, 0, 0, 0]
    for t, c in enumerate(board['auction']):
        if c.upper() not in ('PASS', 'P'):
            n[(dealer + t) % 4] += 1
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', required=True)
    ap.add_argument('--pair', action='append', required=True, help='A:B, reading A against B (empty: no reading)')
    ap.add_argument('--json')
    a = ap.parse_args()
    out = Path(a.out)
    pairs = [tuple(p.split(':', 1)) for p in a.pair]
    names = sorted({x for p in pairs for x in p if x})
    view = Path(tempfile.mkdtemp(prefix='e911-view-'))
    try:
        for q in sorted(out.glob('pools-*-*.npz')):
            files = [out / q.name.replace('pools-', f'fit-{n}-') for n in names]
            if all(f.exists() for f in files):
                for f in [q] + files:
                    (view / f.name).symlink_to(f.resolve())
        rows, _ = bench.read_all(view)
    finally:
        shutil.rmtree(view)
    # per-decision flags from the rpl and uns and tab files, in read_all's order (part by part, decision by decision)
    import gzip
    house, most, n_parts = [], [], 0
    for q in sorted(out.glob('pools-*-*.npz')):
        if not all((out / q.name.replace('pools-', f'fit-{n}-')).exists() for n in names):
            continue
        n_parts += 1
        got, _, _ = bench.load(q)
        with np.load(out / q.name.replace('pools-', 'rpl-')) as z:
            h = z['house']
        with np.load(out / q.name.replace('pools-', 'uns-')) as z:
            hid = z['hidden'].reshape(-1, 2)
        with gzip.open(out / q.name.replace('pools-', 'tab-').replace('.npz', '.json.gz'), 'rt') as f:
            tabs = json.load(f)
        for k, r in enumerate(got):
            seats = [int(s) for s in hid[k]]
            house.append(all(h[k, s] for s in seats))
            c = calls_by_seat(tabs[int(r['table'])]['board'])
            most.append(max(c[s] for s in seats))
    assert len(house) == len(rows), (len(house), len(rows))
    fam = np.array([r['family'] for r in rows])
    tables_n = len({r['uid'] for r in rows})
    share = len(rows) / tables_n
    scored = {}
    for n in names + ['']:
        e, g, eff = [], [], []
        for r in rows:
            fit = r['fit'][n] if n else np.zeros((3, int(r['layouts']) + 1), np.float32)
            s = bench.score(r, fit, 1. if n else 0.)
            g.append(s[0])
            e.append(s[1])
            eff.append(s[4])
        scored[n] = dict(cost=np.array(e), gain=np.array(g), eff=np.array(eff))
    declaring = np.array([bool(r['declaring']) for r in rows])
    regime = np.array([int(r['regime']) for r in rows])
    hh = np.array([bool(r['hidden_house']) for r in rows])
    house, most = np.array(house), np.array(most)
    slices = [('all', np.ones(len(rows), bool)), ('declarer deciding', declaring), ('defender deciding', ~declaring),
              ('before the deal list', regime == 0), ('deal list', regime == 1),
              ('hidden seats played by house bots', hh), ('hidden seats\' calls all the house bidder\'s', house),
              ('hidden seats\' calls not all the house bidder\'s', ~house),
              ('hidden seats only passed', most == 0), ('a hidden seat bid once', most == 1),
              ('a hidden seat bid twice or more', most >= 2)]
    print(f'{len(rows)} decisions on {tables_n} tables of {len(set(fam))} deals ({n_parts} parts); '
          f'{house.mean():.3f} of decisions have every hidden seat\'s calls the house bidder\'s own')
    result = dict(decisions=len(rows), tables=tables_n, deals=len(set(fam)), pairs={})
    for A, B in pairs:
        print(f'\n== {A} against {B or "no reading"}: tricks a board (slice\'s share), nats a decision, effective layouts')
        res = {}
        for label, m in slices:
            d = np.where(m, scored[B]['cost'] - scored[A]['cost'], 0.)
            t, se = bench.mean_se(d, fam)
            dn = scored[A]['gain'][m] - scored[B]['gain'][m]
            nm, nse = bench.mean_se(dn, fam[m]) if m.sum() > 1 else (float('nan'), float('nan'))
            ea, eb = float(np.median(scored[A]['eff'][m])), float(np.median(scored[B]['eff'][m]))
            res[label] = dict(decisions=int(m.sum()), tricks=t * share, se=se * share, nats=nm, nats_se=nse,
                              effective_median=[ea, eb])
            print(f'  {label:48s} {int(m.sum()):6d} decisions | {t * share:+.3f} +- {se * share:.3f} tricks a board | '
                  f'{nm:+.3f} +- {nse:.3f} nats | effective median {ea:.0f} v {eb:.0f}')
        result['pairs'][f'{A}:{B}'] = res
    if a.json:
        Path(a.json).write_text(json.dumps(result, indent=1))


if __name__ == '__main__':
    main()
