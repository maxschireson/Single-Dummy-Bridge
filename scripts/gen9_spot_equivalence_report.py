"""E9-3 tables from rows written by scripts/gen9_spot_equivalence.py."""
import json, sys
from collections import defaultdict
import numpy as np
rows = [json.loads(l) for l in open(sys.argv[1])]
def table(name, key, sel=lambda r: True):
    g = defaultdict(list)
    for r in rows:
        if sel(r):
            g[key(r)].append(r)
    print(f'\n{name}')
    print(f'{"":>22} {"n":>6} {"split%":>7} {"se":>5} {"cost|split":>10} {"lowbest%":>8} {"tiedall%":>8}')
    for k in sorted(g, key=lambda k: (str(type(k)), k)):
        rs = g[k]; n = len(rs); s = np.array([r['split'] for r in rs], float)
        c = [r['cost'] for r in rs if r['split']]
        lb = np.mean([r['lowest_is_best'] for r in rs])
        ts = [r['tied_has_all'] for r in rs if r['played_spot'] and r['tied_known']]
        print(f'{str(k):>22} {n:6d} {100*s.mean():7.2f} {100*np.sqrt(s.mean()*(1-s.mean())/n):5.2f} {np.mean(c) if c else 0:10.2f} {100*lb:8.1f} {100*np.mean(ts) if ts else float("nan"):8.1f}')
D = lambda r: r['role'] == 'defender'
table('all decisions by role', lambda r: r['role'])
table('defenders by situation', lambda r: r['situation'], D)
table('defenders (not leading) by trick', lambda r: r['trick'], lambda r: D(r) and 'lead' not in r['situation'])
table('defenders (not leading) by top spot held', lambda r: r['top_spot'], lambda r: D(r) and 'lead' not in r['situation'])
table('defenders (not leading) by spots held', lambda r: min(r['n_spots'], 5), lambda r: D(r) and 'lead' not in r['situation'])
table('defenders (not leading) by cards left in suit', lambda r: min(r['left_in_suit'], 13) // 2 * 2, lambda r: D(r) and 'lead' not in r['situation'])
table('defenders (not leading): trump suit vs side suit', lambda r: ('side' if r['side_suit'] else 'trump') + '/' + r['strain'], lambda r: D(r) and 'lead' not in r['situation'])
table('defenders (not leading): played a spot?', lambda r: r['played_spot'], lambda r: D(r) and 'lead' not in r['situation'])
table('defenders, follow/discard, trick<=6 vs later', lambda r: (r['situation'], r['trick'] <= 6), lambda r: D(r) and r['situation'] in ('follow_partner','follow_opponent','discard'))
