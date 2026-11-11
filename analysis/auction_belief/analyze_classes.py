import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""Analyse play_classes.py output: whole-play decisions from hand-type classes, scored on the true deal.

If late_classes.py output is present (out/clsx_*), arms netx and exactx use its layout-level picks
in tricks 6-12 and the play_classes.py picks in tricks 1-5.
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from analyze_late import load, declarer_tricks_by_ply, mean_se  # noqa: E402
from bridge_harness.core import Contract, score, imps, vulnerable  # noqa: E402

ARMS = ('v5', 'uniform', 'net', 'exact')
PAIRS = (('net', 'v5'), ('exact', 'v5'), ('exact', 'net'), ('v5', 'uniform'), ('net', 'uniform'))


def main(pattern, pattern_x, pattern_v):
    global ARMS, PAIRS
    rows = load(pattern)
    late = {(r['index'], d['ply']): d for r in load(pattern_x) for d in r['decisions']}
    late_v = {(r['index'], d['ply']): d for r in load(pattern_v) for d in r['decisions']}
    if late:
        ARMS = ARMS + ('netx', 'exactx')
        PAIRS = (('netx', 'v5'), ('exactx', 'v5'), ('exactx', 'netx'), ('netx', 'net'), ('exactx', 'exact')) + PAIRS
    if late and late_v:
        ARMS = ARMS + ('v5x', 'unix')
        PAIRS = (('netx', 'v5x'), ('exactx', 'v5x'), ('v5x', 'v5'), ('v5x', 'unix'), ('v5', 'unix'), ('unix', 'uniform'), ('netx', 'unix')) + PAIRS
    dec, no_exact = [], 0
    for r in rows:
        c = Contract.parse(r['contract'], r['declarer'])
        vul = vulnerable(r['vulnerability'], c.declarer)
        sc = np.array([score(c, t, vul) for t in range(14)], float)
        decl = declarer_tricks_by_ply(r['index'])
        plies = {p['ply']: p for p in r['plies']}
        for d in r['decisions']:
            if 'exact' not in d or d['lp_bidder'] is None:
                no_exact += 1
                continue
            if late:
                x = late.get((r['index'], d['ply']), {})
                d = dict(d, netx=x.get('net_x', d['net']), exactx=x.get('exact_x', d['exact']))
            if late and late_v:
                x = late_v.get((r['index'], d['ply']), {})
                if x:
                    assert abs(x['lp_v5_list'] - d['lp_v5']) < 2e-3, (r['index'], d['ply'])
                d = dict(d, v5x=x.get('v5x', d['v5']), unix=x.get('unix', d['uniform']))
            p = plies[d['ply']]
            true = np.array(p['true_dd'], float)
            declaring = p['actor'] % 2 == c.declarer % 2
            rem = 13 - d['ply'] // 4
            total = decl[d['ply']] + (true if declaring else rem - true)
            s = sc[total.astype(int)] * (1 if declaring else -1)
            row = dict(index=r['index'], trick=d['ply'] // 4 + 1, declaring=declaring, nt=c.trump == 4,
                       i_net=d['lp_net'] - d['lp_cards'], i_bid=d['lp_bidder'] - d['lp_cards'], i_v5=d['lp_v5'] - d['lp_cards'],
                       classes=d['classes'], lp_cards=d['lp_cards'], lp_bidder=d['lp_bidder'],
                       t=(d['t_build'], d['t_score'], d['t_bidder']))
            for a in ARMS:
                row['cost_' + a] = float(true.max() - np.array(d[a]) @ true)
            for a, b in PAIRS:
                wa, wb = np.array(d[a]), np.array(d[b])
                row[f'imp_{a}_{b}'] = float(sum(wa[i] * wb[j] * imps(s[i] - s[j]) for i in np.flatnonzero(wa) for j in np.flatnonzero(wb)))
            dec.append(row)
    deals = sorted({r['index'] for r in rows})

    def by_deal(key, keep=lambda r: True, mean=False):
        tot = {i: 0.0 for i in deals}
        cnt = {i: 0 for i in deals}
        n = 0
        for r in dec:
            if keep(r):
                tot[r['index']] += key(r)
                cnt[r['index']] += 1
                n += 1
        if mean:
            return np.array([tot[i] / cnt[i] for i in deals if cnt[i]]), n
        return np.array([tot[i] for i in deals]), n

    print(f'tables {len(rows)}, decisions {len(dec)} ({len(dec)/max(len(rows),1):.1f} per table); decisions without a bidder-consistent class {no_exact}; '
          f'mean seconds per table {np.mean([r["seconds"] for r in rows]):.1f}')
    segs = (('tricks 1-5', lambda r: r['trick'] <= 5), ('tricks 6-12', lambda r: r['trick'] >= 6), ('all tricks', lambda r: True))
    for name, keep in segs:
        print(f'{name}: double-dummy cost on the true deal, tricks per table (lower is better)')
        print('  ' + '; '.join(f'{a} {mean_se(by_deal(lambda r: r["cost_" + a], keep)[0])[0]:.4f} +- {mean_se(by_deal(lambda r: r["cost_" + a], keep)[0])[1]:.4f}' for a in ARMS))
        for a, b in PAIRS:
            v, n = by_deal(lambda r: r['cost_' + b] - r['cost_' + a], keep)
            m, s = mean_se(v)
            vi, _ = by_deal(lambda r: r[f'imp_{a}_{b}'], keep)
            mi, si = mean_se(vi)
            print(f'  {a:6s} - {b:8s}: {m:+.4f} +- {s:.4f} tricks ({m/s if s > 0 else 0:+.1f} SE); {mi:+.3f} +- {si:.3f} IMPs')
    best = ('netx', 'exactx') if late else ('net', 'exact')
    for name, keep in (('declaring side', lambda r: r['declaring']), ('defenders', lambda r: not r['declaring'])):
        for a, b in ((best[0], 'v5'), (best[1], 'v5')):
            v, n = by_deal(lambda r: r['cost_' + b] - r['cost_' + a], keep)
            m, s = mean_se(v)
            print(f'{name}, all tricks, {a} - {b}: {m:+.4f} +- {s:.4f} ({n} decisions)')
    for name, keep in (('notrump contracts', lambda r: r['nt']), ('suit contracts', lambda r: not r['nt'])):
        ids = sorted({r['index'] for r in dec if keep(r)})
        for x, y in ((best[0], 'v5'), (best[1], 'v5')):
            tot = {i: 0.0 for i in ids}
            for r in dec:
                if keep(r):
                    tot[r['index']] += r['cost_' + y] - r['cost_' + x]
            m, e = mean_se(list(tot.values()))
            print(f'{name} ({len(ids)} tables), all tricks, {x} - {y}: {m:+.4f} +- {e:.4f}')
    print('By trick: paired gains (tricks per table) and information beyond cards and show-outs (nats per decision)')
    print(f'  {"trick":>5} {"n":>5} {best[0] + "-v5":>16} {best[1] + "-v5":>16} {best[1] + "-" + best[0]:>16} | {"v5":>6} {"scorer":>6} {"bidder":>6} {"share":>5} | {"median classes":>14} {"layouts cards":>13} {"bidder":>9}')
    for t in list(range(1, 13)) + ['all']:
        keep = (lambda r: True) if t == 'all' else (lambda r, t=t: r['trick'] == t)
        rs = [r for r in dec if keep(r)]
        if not rs:
            continue
        cells = []
        for a, b in ((best[0], 'v5'), (best[1], 'v5'), (best[1], best[0])):
            v, n = by_deal(lambda r: r['cost_' + b] - r['cost_' + a], keep)
            m, s = mean_se(v)
            cells.append(f'{m:+.4f} +-{s:.4f}')
        v5, n = by_deal(lambda r: r['i_v5'], keep, mean=True)
        ne, _ = by_deal(lambda r: r['i_net'], keep, mean=True)
        bi, _ = by_deal(lambda r: r['i_bid'], keep, mean=True)
        print(f'  {str(t):>5} {n:5d} {cells[0]:>16} {cells[1]:>16} {cells[2]:>16} | {v5.mean():6.2f} {ne.mean():6.2f} {bi.mean():6.2f} {100*ne.mean()/bi.mean():4.0f}% | '
              f'{np.median([r["classes"] for r in rs]):14.0f} {np.exp(np.median([-r["lp_cards"] for r in rs])):13.0f} {np.exp(np.median([-r["lp_bidder"] for r in rs])):9.0f}')
    v5, _ = by_deal(lambda r: r['i_v5'], mean=True)
    ne, _ = by_deal(lambda r: r['i_net'], mean=True)
    bi, _ = by_deal(lambda r: r['i_bid'], mean=True)
    print(f'nats per decision, all tricks: v5 {v5.mean():.3f} +- {mean_se(v5)[1]:.3f}; scorer {ne.mean():.3f} +- {mean_se(ne)[1]:.3f}; bidder {bi.mean():.3f} +- {mean_se(bi)[1]:.3f}')
    tb, _ = by_deal(lambda r: r['t'][0])
    ts, _ = by_deal(lambda r: r['t'][1])
    tx, _ = by_deal(lambda r: r['t'][2])
    print(f'CPU seconds per table (Python/NumPy, one thread): class build {tb.mean():.2f}, scorer {ts.mean():.2f} (max {ts.max():.1f}), bidder check {tx.mean():.2f} (max {tx.max():.1f})')
    worst = sorted((r['t'][1] for r in dec), reverse=True)
    print(f'scorer seconds for one decision: median {np.median([r["t"][1] for r in dec]):.3f}, 99th percentile {np.percentile([r["t"][1] for r in dec], 99):.2f}, max {worst[0]:.1f}; '
          f'classes: median {np.median([r["classes"] for r in dec]):.0f}, max {max(r["classes"] for r in dec)}')
    ev = [r['evaluated'] for r in rows]
    print(f'hand types evaluated per table: scorer mean {np.mean([e["scorer"] for e in ev]):.0f}, bidder mean {np.mean([e["bidder"] for e in ev]):.0f}')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else HERE + '/out/cls_[01].jsonl*', sys.argv[2] if len(sys.argv) > 2 else HERE + '/out/clsx_[01].jsonl*',
         sys.argv[3] if len(sys.argv) > 3 else HERE + '/out/clsv_[01].jsonl*')
