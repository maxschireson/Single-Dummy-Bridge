"""Does the 'no auction' estimate before the deal list depend on the pool size? (It is an importance-weighted estimate on pools drawn by the scorer.)"""
import glob, math, sys
import numpy as np
sys.path.insert(0, '/home/claude/single-dummy-bridge'); sys.path.insert(0, '/home/claude/bench')
from gen8_reading_bench import load, score, mean_se
res = {1: [], 2: [], 4: []}
fam, n_tables, n_dec = [], 0, 0
for part in sorted(glob.glob('/home/claude/pools/pools-*-*.npz')):
    rows, tabs, nets = load(part)
    n_tables += len(tabs)
    with np.load(part.replace('pools-', 'scw-')) as z:
        flat = z['scorer']
    at = 0
    for r in rows:
        L = int(r['layouts'])
        s = flat[at:at + L + 1].astype(np.float64); at += L + 1
        n_dec += 1
        if int(r['regime']) != 0:
            continue
        fit = np.asarray(r['fit']['v4'], np.float64)
        r2 = dict(r); r2['prior'] = r['prior'].astype(np.float64) - s[:L]
        for k in res:
            res[k].append(score(r2, fit, 1., stride=k)[1] - score(r, fit, 1., stride=k)[1])
        fam.append(str(r['family']))
per = n_dec / n_tables
for k, v in res.items():
    m, se = mean_se(np.array(v), np.array(fam))
    print(f'pool 512/{k}: auction given the play reading before the deal list, per decision {m:+.5f} ± {se:.5f}; decisions {len(v)}; a board (x {len(v) / n_tables:.1f}) {m * len(v) / n_tables:+.3f} ± {se * len(v) / n_tables:.3f}')
