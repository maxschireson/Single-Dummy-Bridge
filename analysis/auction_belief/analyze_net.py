import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""Analyse late_net.py output: scorer-weighted lists against v5 and the bidder-built ceiling."""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from analyze_late import load, declarer_tricks_by_ply, mean_se
from bridge_harness.core import Contract, score, imps, vulnerable

ARMS = ('v5', 'uniform', 'net32', 'net', 'blist')
PAIRS = (('net', 'v5'), ('net32', 'v5'), ('blist', 'v5'), ('blist', 'net'), ('net', 'net32'), ('v5', 'uniform'))

def main(pattern):
    rows = load(pattern); dec = []
    for r in rows:
        c = Contract.parse(r['contract'], r['declarer']); vul = vulnerable(r['vulnerability'], c.declarer)
        sc = np.array([score(c, t, vul) for t in range(14)], float)
        decl = declarer_tricks_by_ply(r['index']); plies = {p['ply']: p for p in r['plies']}
        for d in r['decisions']:
            p = plies[d['ply']]; true = np.array(p['true_dd'], float)
            declaring = p['actor'] % 2 == c.declarer % 2; rem = 13 - d['ply'] // 4
            total = decl[d['ply']] + (true if declaring else rem - true)
            s = sc[total.astype(int)] * (1 if declaring else -1)
            row = dict(index=r['index'], trick=d['ply'] // 4 + 1, declaring=declaring,
                       i_net=d['lp_net'] - d['lp_cards'], i_bid=d['lp_bidder'] - d['lp_cards'], i_v5=d['lp_v5'] - d['lp_cards'],
                       n_cards=d['n_cards'], n_bidder=d['n_bidder'], net_eff=d['net_eff'])
            for a in ARMS: row['cost_' + a] = float(true.max() - np.array(d[a]) @ true)
            for a, b in PAIRS:
                wa, wb = np.array(d[a]), np.array(d[b])
                row[f'imp_{a}_{b}'] = float(sum(wa[i] * wb[j] * imps(s[i] - s[j]) for i in np.flatnonzero(wa) for j in np.flatnonzero(wb)))
            dec.append(row)
    deals = sorted({r['index'] for r in dec})
    def by_deal(key, keep=lambda r: True, mean=False):
        tot = {i: 0.0 for i in deals}; cnt = {i: 0 for i in deals}; n = 0
        for r in dec:
            if keep(r): tot[r['index']] += key(r); cnt[r['index']] += 1; n += 1
        if mean: return np.array([tot[i] / cnt[i] for i in deals if cnt[i]]), n
        return np.array([tot[i] for i in deals]), n
    sec = [l['score_seconds'] for r in rows for l in r['start'].values()]
    print(f'tables {len(rows)}, late decisions {len(dec)}; scoring a list takes {np.mean(sec):.3f} s per player (mean), {np.max(sec):.2f} max; mean seconds per table {np.mean([r["seconds"] for r in rows]):.1f}')
    print('Double-dummy cost on the true deal, tricks per table over tricks 6-12 (lower is better)')
    for a in ARMS:
        v, n = by_deal(lambda r: r['cost_' + a]); m, s = mean_se(v); print(f'  {a:8s} {m:.4f} +- {s:.4f}')
    print('Paired, first minus second: tricks per table and IMPs per table (positive favours first)')
    for a, b in PAIRS:
        v, n = by_deal(lambda r: r['cost_' + b] - r['cost_' + a]); m, s = mean_se(v)
        vi, _ = by_deal(lambda r: r[f'imp_{a}_{b}']); mi, si = mean_se(vi)
        print(f'  {a:6s} vs {b:8s}: {m:+.4f} +- {s:.4f} ({m/s:+.1f} SE); {mi:+.3f} +- {si:.3f} IMPs')
    a, _ = by_deal(lambda r: r['cost_v5'] - r['cost_net']); b, _ = by_deal(lambda r: r['cost_v5'] - r['cost_blist'])
    print(f'Share of the bidder-list gain over v5 that the scorer recovers: {100*a.mean()/b.mean():.0f}%')
    print('Information about the true layout beyond cards and show-outs, nats per decision position')
    print(f'  {"trick":>5} {"n":>5} {"v5":>14} {"scorer":>14} {"bidder list":>14} {"scorer share":>12} {"median layouts: cards":>21} {"bidder":>7} {"scorer effective":>16}')
    for t in list(range(6, 13)) + ['all']:
        keep = (lambda r: True) if t == 'all' else (lambda r, t=t: r['trick'] == t)
        v5, n = by_deal(lambda r: r['i_v5'], keep, mean=True); ne, _ = by_deal(lambda r: r['i_net'], keep, mean=True); bi, _ = by_deal(lambda r: r['i_bid'], keep, mean=True)
        rs = [r for r in dec if keep(r)]
        print(f'  {str(t):>5} {n:5d} {v5.mean():+7.3f} +-{mean_se(v5)[1]:.3f} {ne.mean():+7.3f} +-{mean_se(ne)[1]:.3f} {bi.mean():+7.3f} +-{mean_se(bi)[1]:.3f} {100*ne.mean()/bi.mean():11.0f}% {np.median([r["n_cards"] for r in rs]):21.0f} {np.median([r["n_bidder"] for r in rs]):7.0f} {np.median([r["net_eff"] for r in rs]):16.0f}')

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else HERE + '/out/net_[01].jsonl*')
