import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""Analyse late_play3.py output: choice-weighted lists against unweighted lists and v5."""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from analyze_late import load, declarer_tricks_by_ply, mean_se
from bridge_harness.core import Contract, score, imps, vulnerable

ARMS = ('v5', 'uniform', 'list', 'list32', 'wl_u', 'wl_all', 'wl_late')
PAIRS = (('wl_all', 'wl_u'), ('wl_late', 'wl_u'), ('wl_all', 'wl_late'), ('wl_all', 'v5'), ('wl_u', 'v5'), ('list', 'v5'), ('wl_all', 'list'), ('v5', 'uniform'))

def main(pattern):
    rows = load(pattern)
    dec_rows = []
    for r in rows:
        c = Contract.parse(r['contract'], r['declarer']); vul = vulnerable(r['vulnerability'], c.declarer)
        sc = np.array([score(c, t, vul) for t in range(14)], float)
        decl = declarer_tricks_by_ply(r['index']); plies = {p['ply']: p for p in r['plies']}
        for d in r['decisions']:
            p = plies[d['ply']]; true = np.array(p['true_dd'], float)
            declaring = p['actor'] % 2 == c.declarer % 2; rem = 13 - d['ply'] // 4
            total = decl[d['ply']] + (true if declaring else rem - true)
            s = sc[total.astype(int)] * (1 if declaring else -1)
            row = dict(index=r['index'], trick=d['ply'] // 4 + 1, declaring=declaring, n_list=d['n_list'], n_w=d['n_w'],
                       gain_all=d['gain_all'], gain_late=d['gain_late'], ess=d['ess_all'] / d['n_w'])
            for a in ARMS: row['cost_' + a] = float(true.max() - np.array(d[a]) @ true)
            for a, b in PAIRS:
                wa, wb = np.array(d[a]), np.array(d[b])
                row[f'imp_{a}_{b}'] = float(sum(wa[i] * wb[j] * imps(s[i] - s[j]) for i in np.flatnonzero(wa) for j in np.flatnonzero(wb)))
            dec_rows.append(row)
    deals = sorted({r['index'] for r in dec_rows})
    def by_deal(key, keep=lambda r: True, mean=False):
        tot = {i: 0.0 for i in deals}; cnt = {i: 0 for i in deals}; n = 0
        for r in dec_rows:
            if keep(r): tot[r['index']] += key(r); cnt[r['index']] += 1; n += 1
        if mean: return np.array([tot[i] / cnt[i] for i in deals if cnt[i]]), n
        return np.array([tot[i] for i in deals]), n
    print(f'tables {len(rows)}, late decisions {len(dec_rows)}; mean seconds per table {np.mean([r["seconds"] for r in rows]):.1f}')
    print('Double-dummy cost on the true deal, tricks per table over tricks 6-12')
    for a in ARMS:
        v, n = by_deal(lambda r: r['cost_' + a]); m, s = mean_se(v); print(f'  {a:8s} {m:.4f} +- {s:.4f}')
    print('Paired, first minus second: tricks per table, IMPs per table (positive favours first)')
    for a, b in PAIRS:
        v, n = by_deal(lambda r: r['cost_' + b] - r['cost_' + a]); m, s = mean_se(v)
        vi, _ = by_deal(lambda r: r[f'imp_{a}_{b}']); mi, si = mean_se(vi)
        print(f'  {a:8s} vs {b:8s}: {m:+.4f} +- {s:.4f} ({m/s:+.1f} SE); {mi:+.3f} +- {si:.3f} IMPs')
    print('Log posterior gain of the true layout from choice weighting, nats per decision position (mean over tables of per-table means)')
    print(f'  {"trick":>5} {"n":>5} {"all plays":>16} {"plays from trick 6":>20} {"effective share of list":>24}  {"wl_all vs wl_u tricks/table":>28}')
    for t in list(range(6, 13)) + ['all']:
        keep = (lambda r: True) if t == 'all' else (lambda r, t=t: r['trick'] == t)
        ga, n = by_deal(lambda r: r['gain_all'], keep, mean=True); gl, _ = by_deal(lambda r: r['gain_late'], keep, mean=True); es, _ = by_deal(lambda r: r['ess'], keep, mean=True)
        v, _ = by_deal(lambda r: r['cost_wl_u'] - r['cost_wl_all'], keep)
        a1, s1 = mean_se(ga); a2, s2 = mean_se(gl); a3, s3 = mean_se(v)
        print(f'  {str(t):>5} {n:5d} {a1:+8.3f} +- {s1:.3f} {a2:+10.3f} +- {s2:.3f} {100*es.mean():>22.0f}%  {a3:+18.4f} +- {s3:.4f}')
    for name, keep in (('declarer side', lambda r: r['declaring']), ('defenders', lambda r: not r['declaring'])):
        ga, n = by_deal(lambda r: r['gain_all'], keep, mean=True); v, _ = by_deal(lambda r: r['cost_wl_u'] - r['cost_wl_all'], keep)
        a1, s1 = mean_se(ga); a3, s3 = mean_se(v)
        print(f'  {name:14s}: nats {a1:+.3f} +- {s1:.3f}; wl_all vs wl_u {a3:+.4f} +- {s3:.4f} tricks/table ({n} decisions)')

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else HERE + '/out/late3_[01].jsonl*')
