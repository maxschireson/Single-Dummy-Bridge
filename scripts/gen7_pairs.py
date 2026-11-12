#!/usr/bin/env python3
"""Fork pairs of a set of episodes, each tied to its decision's row in the set built from the same episodes.

  python scripts/gen7_pairs.py --episodes DIR --set BUILT.npz --out PAIRS.npz [--workers 4]

A pair is one decision at which two cards were both played out to the end by the same bots: the card
played (A) and a card forced in a fork table (B). Two sources: gap forks (B drawn by its estimated gap,
`gap_forks` in the episode) and audits (`audits`: tie audits, where the search rated B exactly level
with A, and in Gen 7 runs the tree's audits). The pair's label is a result, not an estimate: tricks
with A minus tricks with B, for the side that chose.

BUILT must be the set scripts/gen7_build_dataset.py made from the same directory. Nothing is encoded
again: the builder's order of rows is reproduced from the episodes, and each pair gets the row of its
decision. The reproduction is checked against BUILT (rows per deal, and every row's card and ply).

Arrays (one entry per pair): row, deal, a, b (cards, 13 * suit + rank as in the set), realized
(tricks A - tricks B), imps (IMPs A - IMPs B; NaN where the episode has none), est_a, est_b (the
search's gap to its best card for A and for B), source (0 tie or tree audit, 1 gap fork), band,
propensity, ply, depth (0 = the decision was at a root table), bot (as in the set's meta).
"""
import argparse
import gzip
import json
from multiprocessing import Pool
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.core import Board, card

SKIP = ('replayed_prefix', 'counterfactual_forced', 'forced', 'fixed_opening_lead')
SEATS = 'NESW'


def seat_index(s):
    return SEATS.index(s) if isinstance(s, str) else int(s)


def pairs_of(path):
    """(rows of this episode as (card, ply) in the builder's order, pairs as tuples with a local row)."""
    with gzip.open(path, 'rt') as f:
        d = json.load(f)
    who = {'candidate': d['candidate'], 'opponent': d['opponent']}
    rows, pairs = [], []
    for e in d['unique_tables'].values():
        if e.get('schema_version') == 'v4-passed-out-v1':
            continue
        local = {}
        for ti, table in enumerate(e['tables']):
            for a in table['actions']:
                est = a.get('estimates')
                if a.get('gen6') and est and len(est) > 1 and not any(a.get(k) for k in SKIP):
                    local[(ti, a['ply'])] = len(rows)
                    rows.append((card(a['card']), a['ply']))
        declarer = Board.from_dict(e['board']).contract.declarer        # as the builder reads it
        found = []
        for g in e.get('gap_forks') or []:
            found.append((g.get('parent_table', 0), g['fork_table'], g['ply'], g['forced_card'], 1, g.get('band', -1),
                          g.get('propensity', np.nan), g.get('realized_cost_imps')))
        for x in e.get('audits') or []:
            if x.get('identical_action', True) or x.get('reference_table') is None:
                continue
            found.append((x.get('candidate_table', x['parent_table']), x['reference_table'], x['ply'], x['reference_card'], 0, -1,
                          x.get('audit_probability', np.nan), x.get('gain_imps')))
        for ta, tb, ply, forced, source, band, propensity, imps in found:
            key = (ta, ply)
            if key not in local:
                continue
            root, fork = e['tables'][ta], e['tables'][tb]
            act = root['actions'][ply]
            a, b = card(act['card']), card(forced)
            est = act['estimates']
            if a == b or forced not in est or act['card'] not in est:
                continue
            sign = 1 if seat_index(act['seat']) % 2 == declarer % 2 else -1
            bot = who.get(act['player'], '')
            pairs.append((local[key], a, b, sign * (root['declarer_tricks'] - fork['declarer_tricks']),
                          np.nan if imps is None else float(imps), est[act['card']]['gap_to_best'], est[forced]['gap_to_best'],
                          source, band, propensity, ply, root.get('depth', 0), 0 if bot == '6-32' else 1 if bot == '6-256' else 2))
    return rows, pairs


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--episodes', type=Path, required=True)
    p.add_argument('--set', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--workers', type=int, default=4)
    p.add_argument('--limit', type=int, default=0)
    a = p.parse_args()
    files = sorted(a.episodes.glob('*.json.gz'))
    if a.limit:
        files = files[:a.limit]
    with np.load(a.set) as z:
        deal, meta, families = z['deal'], z['meta'], z['family']
    start = np.searchsorted(deal, np.arange(len(families) + 1))
    out, n_deal, checked = [], 0, 0
    with Pool(a.workers) as pool:
        for i, (rows, pairs) in enumerate(pool.imap(pairs_of, files, chunksize=16)):
            if not rows:
                continue
            lo, hi = start[n_deal], start[n_deal + 1]
            if hi - lo != len(rows) or not np.array_equal(meta[lo:hi, [0, 3]], np.array(rows, np.int32)):
                raise SystemExit(f'{files[i].name}: rows do not match deal {n_deal} of {a.set.name}; is the set built from this directory?')
            checked += len(rows)
            out += [(lo + r, n_deal, *rest) for r, *rest in pairs]
            n_deal += 1
            if (i + 1) % 5000 == 0:
                print(i + 1, 'episodes', len(out), 'pairs', flush=True)
    if n_deal != len(families) or checked != len(deal):
        raise SystemExit(f'{n_deal} deals and {checked} rows reproduced, but the set has {len(families)} and {len(deal)}')
    cols = list(zip(*out)) if out else [[] for _ in range(14)]
    names = ('row', 'deal', 'a', 'b', 'realized', 'imps', 'est_a', 'est_b', 'source', 'band', 'propensity', 'ply', 'depth', 'bot')
    kinds = (np.int64, np.int32, np.int16, np.int16, np.int16, np.float32, np.float32, np.float32, np.int8, np.int8, np.float32, np.int16, np.int8, np.int8)
    arrays = {n: np.array(c, k) for n, c, k in zip(names, cols, kinds)}
    np.savez(a.out, **arrays, family=families)
    r = arrays['realized']
    print(json.dumps(dict(episodes=len(files), deals=n_deal, rows_checked=checked, pairs=len(r), gap_forks=int((arrays['source'] == 1).sum()),
                          audits=int((arrays['source'] == 0).sum()), result_differs=round(float((r != 0).mean()), 4) if len(r) else None,
                          mean_realized=round(float(r.mean()), 4) if len(r) else None)))


if __name__ == '__main__':
    main()
