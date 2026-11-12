#!/usr/bin/env python3
"""Can what a fork really cost, beyond the search's gap, be learned from the policy net's own activations?

  python scripts/plan_fork_fit.py --train forks_train.npz --test forks_fresh.npz [--ceiling ceil16a.json ...]
        [--cards netfeat.json] [--out fit.json]

Rows are scripts/plan_fork_data.py's. The label is one real deal's result (sd about 0.8 tricks a pair); the thing to
learn, the expected cost beyond the search's gap, has an sd of 0.1 to 0.2, so a fit is judged only on deals it did
not see:

  on the fresh forks       realized cost = k + b x gap + c x prediction: c and its error (deals as the unit). c = 1 means
                           the prediction is worth its face value; 0 means it knows nothing.
  on the ceiling's pairs   how much of the variance that real Gen 6 playouts leave after the search's gap the prediction
                           explains (layout luck taken out), and tricks gained by the rule gap + trust x prediction < 0.

Fits: `ridge` is linear in (rank of the card) x (decoder activations of its suit), A's minus B's, plus a few scalars;
`boost` is gradient-boosted trees on the activations of both cards, the trunk and the scalars.
"""
import argparse
import json
import math
import sys

import numpy as np


def load(path):
    z = np.load(path)
    return {k: z[k] for k in z.files}


def scalars(d):
    net = d['net']
    return np.column_stack([d['est'], np.minimum(d['est'], .5), d['trick'] / 13., d['declaring'], d['legal'] / 13., d['position'] / 3., d['dummy'],
                            net[:, 0] - net[:, 1], np.clip(net[:, 3] - net[:, 2], -3, 3), net[:, 4],
                            (d['a'] // 13 == d['b'] // 13).astype(float), (d['a'] % 13 - d['b'] % 13) / 12.])


def ridge_features(d):
    n = len(d['y'])
    phi = np.zeros((n, 13, 257), np.float32)
    i = np.arange(n)
    ra, rb = d['a'].astype(int) % 13, d['b'].astype(int) % 13
    np.add.at(phi, (i, ra), np.column_stack([d['da'], np.ones(n, np.float32)]))
    np.add.at(phi, (i, rb), -np.column_stack([d['db'], np.ones(n, np.float32)]))
    return np.column_stack([phi.reshape(n, -1), scalars(d)])


def boost_features(d):
    return np.column_stack([d['da'], d['db'], d['ha'], scalars(d), d['a'] % 13, d['b'] % 13, d['a'] // 13, d['b'] // 13, d['band']])


def clustered(y, X, groups):
    X = np.column_stack([np.ones(len(y)), X])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    bread = np.linalg.inv(X.T @ X)
    meat = np.zeros((X.shape[1],) * 2)
    for g in np.unique(groups):
        s = X[groups == g].T @ resid[groups == g]
        meat += np.outer(s, s)
    return beta, np.sqrt(np.diag(bread @ meat @ bread))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--train', required=True)
    p.add_argument('--test', required=True)
    p.add_argument('--ceiling', nargs='*', default=[])
    p.add_argument('--cards', help="json of the ceiling pairs' cards (key family|table|ply|table_a|table_b -> a, b)")
    p.add_argument('--fits', default='ridge,boost')
    p.add_argument('--alphas', default='30,100,300,1000,3000')
    p.add_argument('--out')
    a = p.parse_args()
    from sklearn.linear_model import Ridge
    from sklearn.ensemble import HistGradientBoostingRegressor
    tr, te = load(a.train), load(a.test)
    print(f"train {len(tr['y'])} forks on {len(np.unique(tr['family']))} deals; test {len(te['y'])} forks on {len(np.unique(te['family']))} deals")
    target = lambda d: d['y'] - d['est']
    preds = {}
    fold = (tr['family'] % 5).astype(int)
    if 'ridge' in a.fits:
        Xtr, Xte = ridge_features(tr), ridge_features(te)
        mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-6
        Xtr, Xte = (Xtr - mu) / sd, (Xte - mu) / sd
        best = None
        for alpha in [float(x) * len(Xtr) / 1000 for x in a.alphas.split(',')]:
            out = np.zeros(len(Xtr))
            for f in range(5):
                m = Ridge(alpha=alpha).fit(Xtr[fold != f], target(tr)[fold != f])
                out[fold == f] = m.predict(Xtr[fold == f])
            beta, se = clustered(tr['y'], np.column_stack([tr['est'], out]), tr['family'])
            print(f'   ridge alpha {alpha:9.0f}: held-out folds of the training deals: c = {beta[2]:+.3f} +- {se[2]:.3f}, sd of the prediction {out.std():.3f}')
            if best is None or beta[2] / se[2] > best[0]:
                best = (beta[2] / se[2], alpha)
        m = Ridge(alpha=best[1]).fit(Xtr, target(tr))
        preds['ridge'] = m.predict(Xte)
        print(f'   ridge: alpha {best[1]:.0f} kept')
    if 'boost' in a.fits:
        Xtr, Xte = boost_features(tr), boost_features(te)
        m = HistGradientBoostingRegressor(max_iter=300, learning_rate=.03, max_leaf_nodes=15, min_samples_leaf=200, l2_regularization=1.,
                                          early_stopping=True, validation_fraction=.15, random_state=0).fit(Xtr, target(tr))
        preds['boost'] = m.predict(Xte)
        print(f'   boost: {m.n_iter_} rounds')
    preds['constant'] = np.full(len(te['y']), target(tr).mean())
    result = {}
    print('\nOn the fresh forks: realized cost = k + b x gap + c x prediction')
    for name, pr in preds.items():
        if name == 'constant':
            continue
        line = f'   {name:6s}'
        for label, sel in [('all', np.ones(len(pr), bool)), ('gap <= 1/8', te['band'] == 0), ('1/8 to 1/2', te['band'] == 1), ('above', te['band'] == 2),
                           ('tricks 1-2', te['trick'] <= 2), ('3-6', (te['trick'] >= 3) & (te['trick'] <= 6)), ('7+', te['trick'] >= 7)]:
            beta, se = clustered(te['y'][sel], np.column_stack([te['est'][sel], pr[sel]]), te['family'][sel])
            line += f' | {label}: {beta[2]:+.2f} +- {se[2]:.2f}'
            result[f'{name}/{label}'] = (float(beta[2]), float(se[2]), int(sel.sum()))
        print(line + f' | sd of the prediction {pr.std():.3f}')
    if a.ceiling and a.cards:
        cards = json.load(open(a.cards))
        index = {(float(f), int(pl), int(b)): i for i, (f, pl, b) in enumerate(zip(te['family'], te['ply'], te['b']))}   # family is stored as a float
        for path in a.ceiling:
            rows = [r for r in json.load(open(path))['rows'] if r['band'] >= 0]
            t, lk, est, w, fam, at = [], [], [], [], [], []
            for r in rows:
                key = '|'.join(map(str, (r['family'], r['table'], r['ply'], r['table_a'], r['table_b'])))
                i = index.get((float(int(r['family'][:15], 16)), r['ply'], cards[key]['b'])) if key in cards else None
                if i is None:
                    continue
                roll, sh = np.array(r['worlds']['roll'], float), np.array(r['worlds']['share'], float)
                sh = sh / sh.sum()
                d = roll[:, 0] - roll[:, 1]
                n = 1 / (sh ** 2).sum()
                t.append(sh @ d)
                lk.append(((d - sh @ d) ** 2 * sh).sum() / (n - 1) if n > 1.5 else 0.)
                est.append(r['estimated'])
                w.append(1 / r['propensity'])
                fam.append(r['family'])
                at.append(i)
            t, lk, est, w, at = map(np.array, (t, lk, est, w, at))
            fam = np.array(fam)
            sides = 2 * len(set(fam))
            base, _ = clustered(t, est[:, None], fam)
            res0 = np.var(t - np.column_stack([np.ones(len(t)), est]) @ base)
            print(f"\nOn {path}: {len(t)} pairs matched. Variance of the playout mean after the gap alone {res0:.4f}, of which layout luck {lk.mean():.4f}")
            for name, pr in preds.items():
                if name == 'constant':
                    continue
                q = pr[at]
                beta, se = clustered(t, np.column_stack([est, q]), fam)
                res = np.var(t - np.column_stack([np.ones(len(t)), est, q]) @ beta)
                real = res0 - lk.mean()
                line = (f'   {name:6s} coefficient {beta[2]:+.3f} +- {se[2]:.3f}; explains ' + (f'{(res0 - res) / real:.2f}' if real > 1e-4 else 'n/a')
                        + ' of the real variance left by the gap; tricks a side:')
                for trust in (.5, 1., 1.5):
                    play = est + trust * q < -1e-9
                    by = {}
                    for v, g in zip(np.where(play, -t, 0.) * w, fam):
                        by[g] = by.get(g, 0.) + v
                    tot = np.array(list(by.values()))
                    line += f' trust {trust}: {tot.sum() / sides:+.4f} +- {math.sqrt(len(tot) / (len(tot) - 1) * ((tot - tot.mean()) ** 2).sum()) / sides:.4f} ({play.mean():.3f} overruled)'
                print(line)
    if a.out:
        json.dump(result, open(a.out, 'w'))


if __name__ == '__main__':
    sys.exit(main())
