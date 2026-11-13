"""Tables from read_weights.py's lines: how the labels change when the line-choice weights also read the play.

  python read_weights_report.py OUT.jsonl [OUT2.jsonl ...]
"""
import json
import math
import sys

import numpy as np

rows = [json.loads(line) for f in sys.argv[1:] for line in open(f)]
pos = [r for r in rows if not r.get('none')]
deals = len({r['episode'] for r in pos})
print(f'{len(pos)} decisions of the declaring side with {pos[0]["cards"]} cards, in {deals} episodes ({sum(1 for r in rows if r.get("none"))} episodes had none)')
rel_s = [r['true_rel_scorer'] for r in pos if r.get('true_rel_scorer')]
rel_r = [r['true_rel_read'] for r in pos if r.get('true_rel_read')]
print(f'weights computed at {len(rel_s)} of them (the others: every asked target had an outright answer)')
if rel_s:
    gm = lambda v: math.exp(sum(math.log(x) for x in v) / len(v))
    print(f'true layout over the mean layout, geometric mean: scorer {gm(rel_s):.2f}, with the play {gm(rel_r):.2f}')
    print(f'effective layouts, median: scorer {np.median([r["effective_scorer"] for r in pos if "effective_scorer" in r]):.0f}, '
          f'with the play {np.median([r["effective_read"] for r in pos if "effective_read" in r]):.0f}; '
          f'layouts listed, median {np.median([r["layouts"] for r in pos if "layouts" in r]):.0f}; plays read, median {np.median([r["plays"] for r in pos if "plays" in r]):.0f}')
names = {0: 'one down', 1: 'contract', 2: 'overtrick'}
print('target     open  any cert differs  card entries differ  best card differs  best cert differs | best floor: scorer  read | actual in best set: scorer  read')
tot = {}
for t in range(3):
    n = any_diff = ent = ent_diff = best_diff = bc_diff = 0
    fs, fr, cs, cr = [], [], [], []
    ep = []
    for r in pos:
        nd = str(r['need'][t])
        if nd not in r['targets']:
            continue
        s, b = r['targets'][nd]['scorer'], r['targets'][nd]['read']
        if s['guar'] is None or any(s['guar'].values()):
            continue                                        # an outright answer: the weights play no part
        n += 1
        ep.append(r['episode'])
        d = [k for k in s['cert'] if s['cert'][k] is not None and b['cert'].get(k) is not None and s['cert'][k] != b['cert'][k]]
        ent += sum(1 for k in s['cert'] if s['cert'][k] is not None and b['cert'].get(k) is not None)
        ent_diff += len(d)
        any_diff += bool(d)
        best_diff += s['best'] != b['best']
        bc_diff += s['best_cert'] != b['best_cert']
        fs.append(s['best_floor']); fr.append(b['best_floor']); cs.append(s['best_cert'] or 0); cr.append(b['best_cert'] or 0)
    if not n:
        continue
    tot[t] = (n, any_diff, ent, ent_diff, best_diff, bc_diff)
    def se(v):                                              # by episode
        u = {}
        for e, x in zip(ep, v):
            u.setdefault(e, []).append(x)
        m = np.mean(v)
        k = len(u)
        return math.sqrt(k / (k - 1) * sum((sum(x) - m * len(x)) ** 2 for x in u.values())) / len(v) if k > 1 else float('nan')
    diff = [a - b_ for a, b_ in zip(cr, cs)]
    print(f'{names[t]:<10} {n:>4}  {any_diff:>4} ({any_diff / n:5.1%})    {ent_diff:>4} of {ent:<5} ({ent_diff / ent:5.1%})  {best_diff:>4} ({best_diff / n:5.1%})     '
          f'{bc_diff:>4} ({bc_diff / n:5.1%})     |    {np.mean(fs):.3f}  {np.mean(fr):.3f}      |    {np.mean(cs):.3f}+-{se(cs):.3f}  {np.mean(cr):.3f}+-{se(cr):.3f}  (read minus scorer {np.mean(diff):+.3f}+-{se(diff):.3f})')
