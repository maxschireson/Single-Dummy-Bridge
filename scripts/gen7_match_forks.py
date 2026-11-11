#!/usr/bin/env python3
"""The alpha match's own tree forks, rescored for a lower trust or a narrower margin.

Every tree decision records each candidate's gap, tree value and same-layout value, and where the tree changed the
card an audit fork played both cards out. A setting no bolder than the one played switches at a subset of those
decisions, so its switches can be scored from the forks already played.   python scripts/gen7_match_forks.py RUN_DIR [TRUST MARGIN]"""
import collections, glob, gzip, json, math, sys
import numpy as np
SEATS = 'NESW'
idx = lambda s: SEATS.index(s) if isinstance(s, str) else int(s)
run = sys.argv[1]
played = (float(sys.argv[2]), float(sys.argv[3])) if len(sys.argv) > 3 else (.5, .25)
forks = []; boards = set(); tree_decisions = 0
for f in sorted(glob.glob(run + '/episodes/*.json.gz')):
    d = json.load(gzip.open(f)); boards.add(d['index'])
    for tname, tb in d['unique_tables'].items():
        tables = tb['tables']
        if tb['board'].get('declarer') is None or not tables or not tables[0].get('actions'):
            continue
        decl = idx(tb['board']['declarer'])
        audits = {(a['parent_table'], a['ply']): a for a in tb['audits']}
        for ti, t in enumerate(tables):
            nums = [int(x) for x in str(t.get('node', 'root')).split('/') if x.isdigit()]
            fork_ply = nums[-1] if nums else -1
            for a in t['actions']:
                g = a.get('gen7_tree')
                if a['ply'] <= fork_ply or not g or not g.get('consulted'):
                    continue
                tree_decisions += 1
                au = audits.get((ti, a['ply']))
                if au is None or au.get('identical_action', True) or au.get('gain_imps') is None:
                    continue
                ct, rt = tables[au['candidate_table']], tables[au['reference_table']]
                side = 1 if idx(a['seat']) % 2 == decl % 2 else -1
                forks.append(dict(board=d['index'], ply=a['ply'], cands=g['candidates'], card=au['candidate_card'], ref=au['reference_card'],
                                  imps=au['gain_imps'], tricks=side * (ct['declarer_tricks'] - rt['declarer_tricks']), stake=g.get('stake')))
print(f"boards {len(boards)} | tree decisions {tree_decisions} | forks where the tree changed the card {len(forks)}")

def clustered(x, key):
    by = collections.defaultdict(float); n = collections.Counter()
    for v, k in zip(x, key):
        by[k] += v; n[k] += 1
    tot = np.array(list(by.values())); cnt = np.array([n[k] for k in by])
    mean = tot.sum() / max(cnt.sum(), 1)
    se = math.sqrt(((tot - mean * cnt) ** 2).sum() * len(by) / max(1, len(by) - 1)) / max(cnt.sum(), 1) if len(by) > 1 else float('nan')
    return mean, se

def pick(cands, trust, margin):
    near = [c for c in cands if c['gap'] <= margin + 1e-9]
    val = lambda c: -c['gap'] + trust * (c['tree'] - c['same_layouts'])
    top = max(val(c) for c in near)
    return [c for c in near if top - val(c) <= 1e-9]

ok = sum({tuple(c['cards']) for c in pick(x['cands'], *played)} == {tuple(c['cards']) for c in x['cands'] if c['kept']} for x in forks)
print(f"recorded winners reproduced at trust {played[0]}, margin {played[1]}: {ok} of {len(forks)}")
tr = clustered([x['tricks'] for x in forks], [x['board'] for x in forks]); im = clustered([x['imps'] for x in forks], [x['board'] for x in forks])
print(f"all forks as played: {tr[0]:+.3f} +- {tr[1]:.3f} tricks, {im[0]:+.3f} +- {im[1]:.3f} IMPs a fork; totals {sum(x['tricks'] for x in forks):+d} tricks, {sum(x['imps'] for x in forks):+d} IMPs")
print('\n margin  trust | same switch | reverts | other card | tricks a kept fork                  | IMPs a kept fork  | totals: tricks, IMPs')
trusts = [t for t in (1., .75, .5, .375, .3125, .25, .1875, .125) if t <= played[0] + 1e-9]
for margin in [m for m in (.5, .25, .125, .0625) if m <= played[1] + 1e-9]:
    for trust in trusts:
        same, back, other = [], 0, 0
        for x in forks:
            cards = {c for w in pick(x['cands'], trust, margin) for c in w['cards']}
            if x['ref'] in cards: back += 1
            elif x['card'] in cards: same.append(x)
            else: other += 1
        if not same:
            print(f"  {margin:6.4f} {trust:6.4f} | {0:11d} | {back:7d} | {other:10d} |"); continue
        tr = clustered([x['tricks'] for x in same], [x['board'] for x in same]); im = clustered([x['imps'] for x in same], [x['board'] for x in same])
        print(f"  {margin:6.4f} {trust:6.4f} | {len(same):11d} | {back:7d} | {other:10d} | {tr[0]:+.3f} +- {tr[1]:.3f} ({sum(x['tricks'] > 0 for x in same):3d} up, {sum(x['tricks'] < 0 for x in same):3d} down) | {im[0]:+.3f} +- {im[1]:.3f} | "
              f"{sum(x['tricks'] for x in same):+4d}, {sum(x['imps'] for x in same):+4d}")
