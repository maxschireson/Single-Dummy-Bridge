# boxctl: timeout=200
#!/bin/bash
P=$HOME/work/p41; PY=$HOME/work/venv/bin/python
nice -n 19 $PY - <<'PYEOF'
import gzip, json, glob, os, math
import numpy as np
P = os.path.expanduser('~/work/p41')
def cl(x, fam):
    _, inv = np.unique(fam, return_inverse=True)
    t, c = np.bincount(inv, x), np.bincount(inv)
    m, k = t.sum() / c.sum(), len(c)
    return m, math.sqrt(((t - m * c) ** 2).sum() * k / (k - 1)) / c.sum(), k
allp = []
for n in 'ABCDE':
    z = np.load(f'{P}/data/pairs{n}.npz')
    p = {k: z[k] for k in z.files}
    fam = p['family'][p['deal']]
    m = (p['bot'] == 2) & (p['source'] == 0) & (p['est_a'] > p['est_b'] + 1e-9)
    lvl = (p['bot'] == 2) & (p['source'] == 0) & (np.abs(p['est_a'] - p['est_b']) <= 1e-9)
    print(n, 'pairs', len(fam), 'bot2', int((p['bot'] == 2).sum()), 'bot2 audits level', int(lvl.sum()), 'bot2 audits played card rated lower', int(m.sum()),
          'bot2 audits played card rated higher', int(((p['bot'] == 2) & (p['source'] == 0) & (p['est_b'] > p['est_a'] + 1e-9)).sum()),
          'bot0 audits not level', int(((p['bot'] == 0) & (p['source'] == 0) & (np.abs(p['est_a'] - p['est_b']) > 1e-9)).sum()))
    allp.append(dict(set=np.full(m.sum(), n), fam=fam[m], y=p['realized'][m].astype(float), imps=p['imps'][m].astype(float), gap=(p['est_a'] - p['est_b'])[m], ply=p['ply'][m], depth=p['depth'][m]))
c = {k: np.concatenate([x[k] for x in allp]) for k in allp[0]}
print('tricks of the overrides:', np.bincount(c['ply'] // 4 + 1, minlength=14).tolist(), 'depth', np.bincount(c['depth']).tolist())
for label, m in (('all sets', np.ones(len(c['y']), bool)), ('training set (A)', c['set'] == 'A'), ('fresh sets (B-E)', c['set'] != 'A'),
                 ('gap up to 0.1', c['gap'] <= .1), ('gap 0.1 to 0.25', (c['gap'] > .1) & (c['gap'] <= .25)), ('gap over 0.25', c['gap'] > .25)):
    if m.sum() < 30: continue
    a, b = cl(c['y'][m], c['fam'][m]), cl(c['imps'][m][np.isfinite(c['imps'][m])], c['fam'][m][np.isfinite(c['imps'][m])])
    print(f"{label:18s} {int(m.sum()):5d} overrides on {a[2]:4d} deals | played card minus the search's card {a[0]:+.4f} +- {a[1]:.4f} tricks, {b[0]:+.3f} +- {b[1]:.3f} IMPs"
          f" | played better {np.mean(c['y'][m] > 0):.1%}, worse {np.mean(c['y'][m] < 0):.1%} | search's gap {c['gap'][m].mean():.3f}")
# one example, to see what made the bot play a card its search rated lower
done = 0
for f in sorted(glob.glob(f'{P}/epsE/*.json.gz')):
    e = json.load(gzip.open(f, 'rt'))
    if e['candidate'] != '7s-32': continue
    for t in e['unique_tables'].values():
        for x in t.get('audits') or []:
            if x.get('identical_action', True) or x.get('reference_table') is None: continue
            act = t['tables'][x.get('candidate_table', x['parent_table'])]['actions'][x['ply']]
            est = act.get('estimates') or {}
            if act['card'] in est and est[act['card']]['gap_to_best'] > 1e-9:
                print(json.dumps({k: (v if k not in ('estimates', 'gen6', 'behavior_probabilities', 'proposal_probabilities', 'selector_predictions') else '...') for k, v in act.items()})[:1500])
                print('audit', json.dumps(x)[:500]); print('gen7', json.dumps(act.get('gen7'))[:800]); print('est played', est[act['card']], 'ref', est.get(x['reference_card']))
                done += 1
                break
        if done: break
    if done: break
PYEOF
tail -c 100 $P/logs/w768e5.err
