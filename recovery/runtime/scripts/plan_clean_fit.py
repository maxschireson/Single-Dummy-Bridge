#!/usr/bin/env python3
"""Can the correction real playouts make to double dummy be learned from the net's activations when the labels are the
ceiling's playout means (many layouts) instead of one real deal? Cross-validated by deal.

  python scripts/plan_clean_fit.py FORKS.npz EPISODES_DIR LATE_CEILING.json[,MORE.json] EARLY_CEILING.json[,MORE.json]

FORKS.npz is scripts/plan_fork_data.py's file for the same episodes; the ceilings are scripts/plan_ceiling.py's.
"""
import json, gzip, glob, sys, math
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent)); sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plan_fork_fit import load, scalars, boost_features
from bridge_harness.core import card
te = load(sys.argv[1])
index = {(float(f), int(pl), int(b)): i for i, (f, pl, b) in enumerate(zip(te['family'], te['ply'], te['b']))}
LATE, EARLY = sys.argv[3].split(','), sys.argv[4].split(',')
ALL = LATE + EARLY
need = {}
for p in ALL:
    for r in json.load(open(p))['rows']:
        need.setdefault(r['family'], set()).add((r['table'], r['table_b'], r['ply']))
forced = {}
for f in sorted(glob.glob(sys.argv[2] + '/*.json.gz')):
    d = json.load(gzip.open(f, 'rt'))
    for table, tb, ply in need.get(d['family'], ()):
        forced[(d['family'], table, tb, ply)] = card(d['unique_tables'][table]['tables'][tb]['actions'][ply]['card'])
    del d
def rows_of(paths):
    out = []
    for p in paths:
        for r in json.load(open(p))['rows']:
            if r['band'] < 0 or not r.get('worlds'): continue
            b = forced.get((r['family'], r['table'], r['table_b'], r['ply']))
            if b is None: continue
            i = index.get((float(int(r['family'][:15], 16)), r['ply'], b))
            if i is None: continue
            sh = np.array(r['worlds']['share'], float); sh /= sh.sum()
            roll = np.array(r['worlds']['roll'], float); dd = np.array(r['worlds']['dd'], float)
            dplay, ddd = roll[:, 0] - roll[:, 1], dd[:, 0] - dd[:, 1]
            c = dplay - ddd; n = 1 / (sh ** 2).sum()
            out.append(dict(i=i, corr=float(sh @ c), luck=float(((c - sh @ c) ** 2 * sh).sum() / (n - 1)) if n > 1.5 else 0., play=float(sh @ dplay),
                            est=r['estimated'], final=r['final'], fam=r['family'], trick=r['trick']))
    return out
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
for label, paths in (('late ceiling', LATE), ('early ceiling', EARLY)):
    R = rows_of(paths)
    idx = np.array([r['i'] for r in R]); y = np.array([r['corr'] for r in R]); luck = np.array([r['luck'] for r in R]); est = np.array([r['est'] for r in R])
    fams = np.array([r['fam'] for r in R]); uf = sorted(set(fams)); fold = np.array([uf.index(f) % 5 for f in fams])
    sub = {k: v[idx] for k, v in te.items()}
    signal = y.var() - luck.mean()
    print(f'\n{label}: {len(R)} pairs joined on {len(uf)} deals. The correction (playouts - double dummy): variance {y.var():.4f}, of which layout luck {luck.mean():.4f}; real sd {math.sqrt(max(0, signal)):.3f}')
    for name, X in (('scalars', scalars(sub)), ('scalars and activations', boost_features(sub))):
        for fit in ('boost', 'ridge'):
            out = np.zeros(len(y))
            for f in range(5):
                tr_, te_ = fold != f, fold == f
                if fit == 'boost':
                    m = HistGradientBoostingRegressor(max_iter=200, learning_rate=.05, max_leaf_nodes=8, min_samples_leaf=30, l2_regularization=1., random_state=0).fit(X[tr_], y[tr_])
                else:
                    mu, sd = X[tr_].mean(0), X[tr_].std(0) + 1e-6
                    m = Ridge(alpha=300. if X.shape[1] > 50 else 3.).fit((X[tr_] - mu) / sd, y[tr_]); out[te_] = m.predict((X[te_] - mu) / sd); continue
                out[te_] = m.predict(X[te_])
            resid = y - out
            expl = 1 - (resid.var() - luck.mean()) / max(1e-9, signal)
            # bootstrap by deal for the explained share
            rng = np.random.default_rng(0); where = {f: np.where(fams == f)[0] for f in uf}; reps = []
            for _ in range(200):
                pick = np.concatenate([where[uf[j]] for j in rng.integers(0, len(uf), len(uf))])
                sg = y[pick].var() - luck[pick].mean(); reps.append(1 - (resid[pick].var() - luck[pick].mean()) / max(1e-9, sg))
            slope = np.polyfit(out, y, 1)[0] if out.std() > 1e-9 else float('nan')
            print(f'   {name:24s} {fit:5s}: explains {expl:+.3f} +- {np.std(reps):.3f} of the real correction; slope of the correction on the prediction {slope:+.2f}; sd of the prediction {out.std():.3f}')
