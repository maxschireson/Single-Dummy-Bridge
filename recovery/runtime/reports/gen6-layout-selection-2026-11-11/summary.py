"""Summary of the layout-selection records in this folder (needs NumPy only): python summary.py"""
import glob
import gzip
import json
import os

import numpy as np


def load(pattern):
    rows = {}
    for f in sorted(glob.glob(pattern)):
        for line in gzip.open(f, 'rt'):
            r = json.loads(line)
            rows[r['index']] = r
    return [rows[k] for k in sorted(rows)]


def mean_se(x):
    x = np.asarray(x, float)
    return x.mean(), x.std(ddof=1) / np.sqrt(len(x))


rows = load(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sel_[01].jsonl.gz'))
def table(rows, schemes, pairs, title):
    dec = []
    for r in rows:
        for d in r['decisions']:
            ref = np.array(d['ref']); row = dict(index=r['index'], trick=d['ply'] // 4 + 1)
            for s, w in d['picks'].items(): row[s] = float(ref.max() - np.array(w) @ ref)
            dec.append(row)
    deals = sorted({r['index'] for r in dec})
    def by(key, keep=lambda r: True):
        tot = {i: 0.0 for i in deals}
        for r in dec:
            if keep(r): tot[r['index']] += key(r)
        return np.array([tot[i] for i in deals])
    print(f'{title}: tables {len(rows)} (indices {min(deals)}-{max(deals)}), decisions {len(dec)}')
    for s in schemes:
        a = mean_se(by(lambda r: r[s])); b = mean_se(by(lambda r: r[s], lambda r: r['trick'] <= 2)); c = mean_se(by(lambda r: r[s], lambda r: r['trick'] >= 3))
        print(f'  {s:9s} loss {a[0]:.4f} +-{a[1]:.4f} | tricks 1-2 {b[0]:.4f} +-{b[1]:.4f} | tricks 3-5 {c[0]:.4f} +-{c[1]:.4f}')
    for x, y in pairs:
        out = []
        for keep in (lambda r: True, lambda r: r['trick'] <= 2, lambda r: r['trick'] >= 3):
            m, e = mean_se(by(lambda r: r[y] - r[x], keep)); out.append(f'{m:+.4f} +-{e:.4f}')
        print(f'  {x} better than {y} by: ' + ' | '.join(out))
new = [r for r in rows if r['decisions'] and 'sys64' in r['decisions'][0]['picks']]
table(new, ('iid_32', 'sys32', 'strat_32', 'iid_64', 'sys64', 'med_64', 'strat_64', 'iid_128', 'iid_256'),
      (('sys64', 'iid_64'), ('sys64', 'med_64'), ('sys64', 'strat_64'), ('sys64', 'sys32'), ('sys64', 'iid_128'), ('iid_256', 'sys64')), 'tables with the sys64 arm')
table(rows, ('iid_32', 'sys32', 'med_32', 'strat_32', 'top32', 'iid_64', 'med_64', 'strat_64', 'iid_128', 'iid_256'),
      (('sys32', 'iid_32'), ('strat_32', 'iid_32'), ('med_32', 'iid_32'), ('strat_32', 'sys32'), ('iid_64', 'iid_32'), ('iid_64', 'strat_32'), ('iid_64', 'sys32'), ('med_64', 'iid_64'), ('strat_64', 'iid_64'), ('iid_128', 'iid_32'), ('iid_256', 'iid_32'), ('iid_32', 'top32')), 'all tables')
