import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""Compare the joint prototype's layouts with belief, uniform and exact layouts on the same leads."""
import json, sys
import numpy as np
sys.path.insert(0, HERE); sys.path.insert(0, RUNTIME)
from analyze_leads import load, pick, subsets
from analyze_leads2 import lead_table, mean_se, IMP

def main(eval_glob):
    main_rows = {r['index']: r for r in load(HERE + '/out/main_*.jsonl*') if not r.get('passed_out')}
    ev = {r['index']: r for r in load(eval_glob)}
    try: info = {int(k): v for k, v in json.load(open(HERE + '/out/info.json')).items()}
    except Exception: info = {}
    common = sorted(set(main_rows) & set(ev))
    arms = ['model32', 'hybrid32', 'belief32', 'belief128', 'uniform32']
    diffs = {k: [] for k in [('model32', 'belief32'), ('hybrid32', 'belief32'), ('exact32', 'belief32'), ('exact32', 'model32'), ('exact32', 'hybrid32'),
                             ('model32', 'belief128'), ('hybrid32', 'belief128'), ('model32', 'uniform32')]}
    dimp = {k: [] for k in diffs}
    filt_only = {k: [] for k in [('filtered32', 'belief32'), ('exact32', 'filtered32'), ('exact32', 'belief32')]}
    nat, avail, capt, pass_rate, have_filtered, props = [], [], [], [], [], []
    for i in common:
        r, e = main_rows[i], ev[i]
        if len(r['exact_dd']) < 64: continue
        c, sc = lead_table(r)
        E = np.array(r['exact_dd'], int)[:64]
        halves = [np.arange(0, 32), np.arange(32, 64)]
        def picks_of(dd, size):
            dd = np.array(dd, float)
            return [pick(dd[ix]) for ix in subsets(len(dd), size)]
        P = dict(belief32=picks_of(r['belief_dd'], 32), belief128=picks_of(r['belief_dd'], 128), uniform32=picks_of(r['uniform_dd'], 32),
                 model32=picks_of(e['model_dd'], 32))
        filt = picks_of(e['filtered_dd'], 32) if len(e['filtered_dd']) >= 32 else []
        P['hybrid32'] = filt if filt else P['model32']
        ex = [pick(E[h].astype(float)) for h in halves]
        def val(w, evs): return float(w @ evs.mean(axis=0))
        def impg(wa, wb, evs):
            s = sc[13 - evs]
            return float(sum(wa[a] * wb[b] * IMP(s[:, b] - s[:, a]).mean() for a in np.flatnonzero(wa) for b in np.flatnonzero(wb)))
        def cmp(a, b):
            if a == 'exact32':
                t = [val(ex[f], E[halves[1 - f]]) - val(w, E[halves[1 - f]]) for f in (0, 1) for w in P[b]]
                m = [impg(ex[f], w, E[halves[1 - f]]) for f in (0, 1) for w in P[b]]
            else:
                t = [val(wa, E) - val(wb, E) for wa in P[a] for wb in P[b]]
                m = [impg(wa, wb, E) for wa in P[a] for wb in P[b]]
            return np.mean(t), np.mean(m)
        for k in diffs:
            t, m = cmp(*k); diffs[k].append(t); dimp[k].append(m)
        if filt:
            P['filtered32'] = filt
            for k in filt_only:
                filt_only[k].append(cmp(*k)[0])
        nat.append(e['nats']); pass_rate.append(e['pass_first256']); have_filtered.append(bool(filt)); props.append(e['proposals'] / max(e['passed'], 1))
        if i in info: avail.append(info[i][0]); capt.append(info[i][1])
    n = len(nat)
    print(f'leads {n}')
    print('Posterior yardstick, first minus second, per lead: tricks and IMPs (positive favours first)')
    for k in diffs:
        a, b = mean_se(diffs[k]); c1, d1 = mean_se(dimp[k])
        print(f'  {k[0]:9s} vs {k[1]:9s}: {a:+.4f} +- {b:.4f} ({a/b:+.1f} SE); {c1:+.3f} +- {d1:.3f} IMPs')
    a = np.mean(diffs[('model32', 'belief32')]); h = np.mean(diffs[('hybrid32', 'belief32')]); x = np.mean(diffs[('exact32', 'belief32')])
    print(f'Share of the exact-over-belief gain recovered: plain model {100*a/x:.0f}%, with bidder filter {100*h/x:.0f}%')
    print(f'Leads where 32+ filtered layouts were found within the proposal budget: {np.mean(have_filtered)*100:.0f}%; on those leads:')
    for k in filt_only:
        a, b = mean_se(filt_only[k]); print(f'  {k[0]:10s} vs {k[1]:10s}: {a:+.4f} +- {b:.4f} (n={len(filt_only[k])})')
    pr = np.array(pass_rate)
    print(f'Bidder pass rate of model layouts: mean {pr.mean()*100:.1f}%, median {np.median(pr)*100:.1f}%, leads at zero of 256: {np.mean(pr==0)*100:.0f}%; proposals per kept layout: median {np.median(props):.1f}')
    pairs = [(-info[i][0], ev[i]['log_u_from_model']) for i in common if i in info and ev[i].get('log_u_from_model') is not None]
    if pairs:
        x = np.array(pairs); d = x[:, 1] - x[:, 0]
        print(f'Cross-check of the consistent share: log u from rejection {x[:,0].mean():.2f}, from model importance weights {x[:,1].mean():.2f}; '
              f'difference {d.mean():+.3f} +- {d.std(ddof=1)/np.sqrt(len(d)):.3f} (n={len(d)}), correlation {np.corrcoef(x[:,0], x[:,1])[0,1]:.3f}')
    ess = np.array([ev[i]['ess'] for i in common]); kept = np.array([max(ev[i]['passed'], 1) for i in common])
    print(f'Importance weights of filtered layouts (target = exact posterior): effective sample share median {np.median(ess/kept)*100:.0f}%, mean {np.mean(ess/kept)*100:.0f}%')
    a, b = mean_se(nat); print(f'Nats over uniform on these leads: model {a:.2f} +- {b:.2f}', end='')
    if avail:
        print(f'; belief sampler {np.mean(capt):.2f} +- {mean_se(capt)[1]:.2f}; available {np.mean(avail):.2f} +- {mean_se(avail)[1]:.2f} (n={len(avail)})')
    else: print()

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else HERE + '/out/eval_*.jsonl*')
