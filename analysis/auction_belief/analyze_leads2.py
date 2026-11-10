import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""Lead comparison with two yardsticks.

(1) True deal: double-dummy cost of each arm's chosen lead on the actual layout.
(2) Posterior value: the same lead scored on exact-posterior layouts that were
    NOT used to choose it. The true deal is one draw from that posterior, so (2)
    estimates the same expectation as (1) with far less noise. For the exact arm
    the 64 exact layouts are split in halves: choose on one, score on the other.
"""
import sys

import numpy as np

sys.path.insert(0, HERE)
sys.path.insert(0, RUNTIME)
from analyze_leads import load, pick, subsets  # noqa: E402
from bridge_harness.core import Contract, score, imps, vulnerable  # noqa: E402

IMP = np.vectorize(imps)


def mean_se(x):
    x = np.asarray(x, float)
    return x.mean(), x.std(ddof=1) / np.sqrt(len(x))


def lead_table(r):
    c = Contract.parse(r['contract'], r['declarer'])
    vul = vulnerable(r['vulnerability'], c.declarer)
    sc = np.array([score(c, t, vul) for t in range(14)], float)   # declarer score by declarer tricks
    return c, sc


def run(rows, exclude_capped=False, label='', keep=None, brief=False):
    arms = {'belief32': ('belief', 32), 'belief64': ('belief', 64), 'belief128': ('belief', 128), 'uniform32': ('uniform', 32)}
    d_tr = {k: [] for k in arms}      # exact32 minus arm, tricks, posterior yardstick (cross-fitted)
    d_im = {k: [] for k in arms}
    t_tr = {k: [] for k in arms}      # same on the true deal
    t_im = {k: [] for k in arms}
    val = {k: [] for k in list(arms) + ['exact32']}   # posterior value of chosen lead minus posterior-best (regret), eval on held-out half
    among = {('belief32', 'uniform32'): [], ('belief64', 'belief32'): [], ('belief128', 'belief32'): [], ('belief128', 'belief64'): []}
    among_im = {k: [] for k in among}
    n = 0
    for r in rows:
        if r.get('passed_out') or len(r.get('exact_dd', [])) < 64:
            continue
        if exclude_capped and r['exact_stats']['capped']:
            continue
        if keep is not None and not keep(r):
            continue
        n += 1
        c, sc = lead_table(r)
        true = np.array(r['true_dd'], int)
        E = np.array(r['exact_dd'], int)[:64]
        halves = [np.arange(0, 32), np.arange(32, 64)]
        picks = {}
        for k, (name, size) in arms.items():
            dd = np.array(r[name + '_dd'], float)
            picks[k] = [pick(dd[ix]) for ix in subsets(len(dd), size)]
        ex = [pick(E[h].astype(float)) for h in halves]

        def value(w, ev):            # mean leader-side tricks of a (tie-weighted) lead on eval layouts
            return float(w @ ev.mean(axis=0))

        def imp_gain(wa, wb, ev):    # expected IMPs to lead a over lead b, averaged over eval layouts
            s = sc[13 - ev]          # (worlds, leads) declarer scores
            ia, ib = np.flatnonzero(wa), np.flatnonzero(wb)
            tot = 0.
            for i in ia:
                for j in ib:
                    tot += wa[i] * wb[j] * IMP(s[:, j] - s[:, i]).mean()
            return float(tot)

        for k in arms:
            dt, di = [], []
            for f in (0, 1):
                ev = E[halves[1 - f]]
                for w in picks[k]:
                    dt.append(value(ex[f], ev) - value(w, ev))
                    di.append(imp_gain(ex[f], w, ev))
            d_tr[k].append(np.mean(dt)); d_im[k].append(np.mean(di))
            tt = np.mean([ex[f] @ true - w @ true for f in (0, 1) for w in picks[k]])
            ti = np.mean([imp_gain(ex[f], w, true[None, :]) for f in (0, 1) for w in picks[k]])
            t_tr[k].append(tt); t_im[k].append(ti)
        for (a, b) in among:
            among[(a, b)].append(np.mean([value(wa, E) - value(wb, E) for wa in picks[a] for wb in picks[b]]))
            among_im[(a, b)].append(np.mean([imp_gain(wa, wb, E) for wa in picks[a] for wb in picks[b]]))
        # regret against the held-out posterior-best lead (optimistic by the max, same for every arm)
        for f in (0, 1):
            ev = E[halves[1 - f]].mean(axis=0)
            val['exact32'].append(ev.max() - ex[f] @ ev)
        for k in arms:
            ev = E.mean(axis=0)
            val[k].append(np.mean([ev.max() - w @ ev for w in picks[k]]))
    if brief:
        a, b = mean_se(d_tr['belief32']); c1, d1 = mean_se(d_im['belief32']); e, f = mean_se(d_tr['uniform32']); g, h = mean_se(among[('belief128', 'belief32')])
        print(f'  {label:34s} n={n:4d}  exact32-belief32 {a:+.4f} +- {b:.4f} tricks, {c1:+.3f} +- {d1:.3f} IMPs | exact32-uniform32 {e:+.4f} +- {f:.4f} | belief128-belief32 {g:+.4f} +- {h:.4f}')
        return None
    print(f'--- {label} leads {n}' + (' (capped leads excluded)' if exclude_capped else ''))
    print('exact-32 minus arm, per lead (positive = exact layouts choose the better lead)')
    print('  arm          posterior yardstick: tricks, IMPs            true deal: tricks, IMPs')
    out = {}
    for k in arms:
        a, b = mean_se(d_tr[k]); c1, d1 = mean_se(d_im[k]); e, f = mean_se(t_tr[k]); g, h = mean_se(t_im[k])
        out[k] = dict(post_tricks=(a, b), post_imps=(c1, d1), true_tricks=(e, f), true_imps=(g, h))
        print(f'  {k:10s}  {a:+.4f} +- {b:.4f} ({a/b:+.1f} SE), {c1:+.3f} +- {d1:.3f}     {e:+.4f} +- {f:.4f}, {g:+.3f} +- {h:.3f}')
    print('regret against the best lead on held-out exact layouts, tricks (exact32 scored on 32 held-out layouts, others on 64; levels are optimistic by the max)')
    for k in ['exact32'] + list(arms):
        a, b = mean_se(val[k]) if k != 'exact32' else mean_se(np.array(val[k]).reshape(-1, 2).mean(1))
        print(f'  {k:10s} {a:.4f} +- {b:.4f}')
    print('other pairs, first minus second, posterior yardstick (all 64 exact layouts)')
    for k in among:
        a, b = mean_se(among[k]); c1, d1 = mean_se(among_im[k])
        out[k] = dict(post_tricks=(a, b), post_imps=(c1, d1))
        print(f'  {k[0]:10s} vs {k[1]:10s} {a:+.4f} +- {b:.4f} ({a/b:+.1f} SE), {c1:+.3f} +- {d1:.3f} IMPs')
    return out


if __name__ == '__main__':
    rows = load(sys.argv[1] if len(sys.argv) > 1 else HERE + '/out/main_*.jsonl*')
    rows = [r for r in rows if not r.get('passed_out')]
    run(rows, label='all')
    print('Subgroups (posterior yardstick):')
    run(rows, label='capped excluded', exclude_capped=True, brief=True)
    run(rows, label='plain rejection only (independent)', keep=lambda r: r['exact_stats']['rounds'] == 0, brief=True)
    run(rows, label='later rounds used', keep=lambda r: r['exact_stats']['rounds'] > 0, brief=True)
    run(rows, label='notrump contracts', keep=lambda r: r['contract'][1] == 'N', brief=True)
    run(rows, label='suit contracts', keep=lambda r: r['contract'][1] != 'N', brief=True)
    run(rows, label='level 1-2', keep=lambda r: int(r['contract'][0]) <= 2, brief=True)
    run(rows, label='level 3-4', keep=lambda r: int(r['contract'][0]) in (3, 4), brief=True)
    run(rows, label='level 5-7', keep=lambda r: int(r['contract'][0]) >= 5, brief=True)
    acc = sorted(r['exact_stats']['checks'] for r in rows)
    med = acc[len(acc) // 2]
    run(rows, label='tighter auctions (more sampler work)', keep=lambda r: r['exact_stats']['checks'] > med, brief=True)
    run(rows, label='looser auctions', keep=lambda r: r['exact_stats']['checks'] <= med, brief=True)
