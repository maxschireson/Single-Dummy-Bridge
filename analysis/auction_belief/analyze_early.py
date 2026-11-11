import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""Analyse early_play.py output (tricks 1-5 after the lead), scored on the true deal."""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from analyze_late import load, declarer_tricks_by_ply, mean_se
from bridge_harness.core import Contract, score, imps, vulnerable

def main(pattern):
    rows = load(pattern); dec = []
    skipped = 0
    for r in rows:
        c = Contract.parse(r['contract'], r['declarer']); vul = vulnerable(r['vulnerability'], c.declarer)
        sc = np.array([score(c, t, vul) for t in range(14)], float)
        decl = declarer_tricks_by_ply(r['index']); plies = {p['ply']: p for p in r['plies']}
        for d in r['decisions']:
            if 'v5' not in d: skipped += 1; continue
            p = plies[d['ply']]; true = np.array(p['true_dd'], float)
            declaring = p['actor'] % 2 == c.declarer % 2; rem = 13 - d['ply'] // 4
            total = decl[d['ply']] + (true if declaring else rem - true)
            s = sc[total.astype(int)] * (1 if declaring else -1)
            row = dict(index=r['index'], trick=d['ply'] // 4 + 1, declaring=declaring, s=s, true=true, d=d)
            dec.append(row)
    arms = [a for a in ('v5', 'uniform', 'net32', 'exact32', 'exact64') if dec and a in dec[0]['d']]
    deals = sorted({r['index'] for r in dec})
    def by_deal(key, keep=lambda r: True):
        tot = {i: 0.0 for i in deals}; n = 0
        for r in dec:
            if keep(r): tot[r['index']] += key(r); n += 1
        return np.array([tot[i] for i in deals]), n
    cost = lambda r, a: float(r['true'].max() - np.array(r['d'][a]) @ r['true'])
    def imp(r, a, b):
        wa, wb = np.array(r['d'][a]), np.array(r['d'][b])
        return float(sum(wa[i] * wb[j] * imps(r['s'][i] - r['s'][j]) for i in np.flatnonzero(wa) for j in np.flatnonzero(wb)))
    print(f'tables {len(rows)}, decisions in tricks 1-5 after the lead {len(dec)} ({len(dec)/max(len(rows),1):.1f} per table); skipped for lack of exact layouts {skipped}; mean seconds per table {np.mean([r["seconds"] for r in rows]):.1f}')
    print('Double-dummy cost on the true deal, tricks per table over tricks 1-5 (lower is better)')
    for a in arms:
        v, n = by_deal(lambda r: cost(r, a)); m, s = mean_se(v); print(f'  {a:8s} {m:.4f} +- {s:.4f}')
    pairs = [p for p in (('exact32', 'v5'), ('exact64', 'v5'), ('net32', 'v5'), ('exact32', 'net32'), ('exact64', 'exact32'), ('v5', 'uniform')) if p[0] in arms and p[1] in arms]
    print('Paired, first minus second: tricks per table and IMPs per table (positive favours first)')
    for a, b in pairs:
        v, n = by_deal(lambda r: cost(r, b) - cost(r, a)); m, s = mean_se(v)
        vi, _ = by_deal(lambda r: imp(r, a, b)); mi, si = mean_se(vi)
        print(f'  {a:8s} vs {b:8s}: {m:+.4f} +- {s:.4f} ({m/s:+.1f} SE); {mi:+.3f} +- {si:.3f} IMPs')
    if 'net32_eff' in dec[0]['d']:
        print(f'scorer weights: median effective sample of 4,096 uniform proposals {np.median([r["d"]["net32_eff"] for r in dec]):.0f}; below 32 in {100*np.mean([r["d"]["net32_eff"] < 32 for r in dec]):.0f}% of decisions')

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else HERE + '/out/early_[01].jsonl*')
