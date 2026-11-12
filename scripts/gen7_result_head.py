#!/usr/bin/env python3
"""A head trained on fork results, on a frozen policy net, scored on unseen pairs against the search's own gap.

  python scripts/gen7_result_head.py --net POLICY.npz --set TRAIN.npz --pairs PAIRS.npz \
         --test FRESH.npz FRESH_PAIRS.npz [--test ...] --out DIR

The question (experiment E2 on the fleet queue): a fork pair records what a forced card B really did
against the card played A. Does a head trained on those results predict the result on pairs it has not
seen better than the search's own estimate of the gap? If so, forks are worth more of the collectors' time.

The head is one more channel on the net's per-suit decoder: for a card of rank r in suit s it is
d[s] . W[:, r] + c[r], with d the decoder's hidden layer for that suit (frozen). A pair's prediction is
head(B) - head(A) with the sign turned so that it predicts tricks(A) - tricks(B), the cost of B. W is
fitted by ridge regression on the training pairs (closed form), the ridge strength chosen on a tenth
of the training deals. Nothing else in the net moves.

Models, all fitted on the training pairs and scored on the test pairs by squared error against the
realized cost of B, with intervals from bootstrap draws of deals:
  zero        predict 0
  search      the search's estimated gap of B minus that of A, as recorded
  search*     the same times a fitted slope
  gap head    the net's own gap head (trained to copy the search, never on results), times a fitted slope
  result      the result head alone
  search+res  fitted slope on the search's gap, plus the result head
Test pairs come from sets of boards fetched after the training set; deals the training set has are dropped.
"""
import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from bridge_harness.gen7_net import CARD_FEATURES, INPUTS, SEAT_SHOWN, SUIT_SHOWN, features, relu
from train_gen7_policy import stored_arrays


def hidden(params, batch):
    """(decoder hidden layer per suit [n, 4, 2e], gap head [n, 52]) of a suit net: forward() up to its last layer."""
    cards, g = features(batch, np)
    n = cards.shape[0]
    shown = np.asarray(batch['shown']).astype(np.float32).reshape(n, 4, SEAT_SHOWN)[:, :, :SUIT_SHOWN * 4]
    about_suit = np.transpose(shown.reshape(n, 4, SUIT_SHOWN, 4), (0, 3, 1, 2)).reshape(n, 4, 4 * SUIT_SHOWN)
    s = np.concatenate([cards.reshape(n, 4, 13 * CARD_FEATURES), about_suit], axis=2)
    s = relu(s @ params['ws0'] + params['bs0'], np)
    s = relu(s @ params['ws1'] + params['bs1'], np)
    h = np.concatenate([s.reshape(n, -1), g], axis=1)
    h = relu(h @ params['wt0'] + params['bt0'], np)
    h = relu(h @ params['wt1'] + params['bt1'], np)
    slot = np.broadcast_to(np.eye(4, dtype=np.float32)[None], (n, 4, 4))
    d = np.concatenate([s, np.broadcast_to(h[:, None, :], (n, 4, h.shape[1])), slot], axis=2)
    d = relu(d @ params['wd0'] + params['bd0'], np)
    out = (d @ params['wd1'] + params['bd1']).reshape(n, 4, 13, 5)
    return d, out[..., 1].reshape(n, 52)


class Pairs:
    """A pair set with the frozen net's features at each pair's decision."""

    def __init__(self, params, set_path, pairs_path, drop=None, chunk=4096):
        with np.load(pairs_path) as z:
            p = {k: z[k] for k in z.files}
        keep = np.ones(len(p['row']), bool)
        if drop is not None:
            keep = ~np.isin(p['family'][p['deal']], drop)
        self.family = p['family']
        self.p = {k: v[keep] for k, v in p.items() if k != 'family'}
        self.dropped = int((~keep).sum())
        data = stored_arrays(set_path)
        rows, inverse = np.unique(self.p['row'], return_inverse=True)
        d, gap = [], []
        for i in range(0, len(rows), chunk):
            r = rows[i:i + chunk]
            di, gi = hidden(params, {k: np.asarray(data[k][r]) for k in INPUTS})
            d.append(di.astype(np.float32))
            gap.append(gi.astype(np.float32))
        self.d = np.concatenate(d) if d else np.zeros((0, 4, 1), np.float32)
        self.gap_head = np.concatenate(gap) if gap else np.zeros((0, 52), np.float32)
        self.at = inverse
        self.n = len(self.p['row'])
        self.y = self.p['realized'].astype(np.float64)
        self.search = (self.p['est_b'] - self.p['est_a']).astype(np.float64)
        self.net_gap = (self.gap_head[self.at, self.p['b']] - self.gap_head[self.at, self.p['a']]).astype(np.float64)

    def design(self, lo, hi):
        """Rows lo:hi of the head's design: for each rank, d of B's suit where B has that rank minus the same for A; then rank offsets."""
        idx = np.arange(lo, hi)
        at, a, b = self.at[idx], self.p['a'][idx].astype(np.int64), self.p['b'][idx].astype(np.int64)
        width = self.d.shape[2]
        x = np.zeros((len(idx), 13, width + 1), np.float32)
        r = np.arange(len(idx))                             # one entry per row, so plain indexed updates are exact
        x[r, b % 13, :width] += self.d[at, b // 13]
        x[r, b % 13, width] += 1.
        x[r, a % 13, :width] -= self.d[at, a // 13]
        x[r, a % 13, width] -= 1.
        return x.reshape(len(idx), -1)

    def moments(self, mask, chunk=20000):
        """X'X, X'y, and the head's design times each scalar feature, over the pairs in mask (columns: head, search, net gap)."""
        k = 13 * (self.d.shape[2] + 1)
        xtx, xty = np.zeros((k + 2, k + 2)), np.zeros(k + 2)
        for lo in range(0, self.n, chunk):
            hi = min(self.n, lo + chunk)
            m = mask[lo:hi]
            if not m.any():
                continue
            x = np.concatenate([self.design(lo, hi), self.search[lo:hi, None].astype(np.float32), self.net_gap[lo:hi, None].astype(np.float32)], axis=1)[m]
            xtx += x.T @ x                                  # single-precision products, summed in double
            xty += x.T.astype(np.float64) @ self.y[lo:hi][m]
        return xtx, xty

    def predict(self, w, chunk=20000):
        """Prediction with weights over (head columns, search, net gap)."""
        out = np.empty(self.n)
        k = len(w) - 2
        for lo in range(0, self.n, chunk):
            hi = min(self.n, lo + chunk)
            out[lo:hi] = self.design(lo, hi).astype(np.float64) @ w[:k] + w[k] * self.search[lo:hi] + w[k + 1] * self.net_gap[lo:hi]
        return out


def solve(xtx, xty, cols, ridge_on, lam):
    """Least squares on the columns `cols`, with ridge `lam` on those of them listed in `ridge_on`."""
    a = xtx[np.ix_(cols, cols)].copy()
    pen = np.isin(cols, ridge_on)
    a[np.diag_indices(len(cols))] += lam * pen + 1e-9
    w = np.zeros(len(xty))
    w[cols] = np.linalg.solve(a, xty[cols])
    return w


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--net', type=Path, required=True)
    p.add_argument('--set', type=Path, required=True)
    p.add_argument('--pairs', type=Path, required=True)
    p.add_argument('--test', nargs=2, action='append', required=True, metavar=('SET', 'PAIRS'))
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    with np.load(a.net) as f:
        params = {k: f[k] for k in f.files}
    train = Pairs(params, a.set, a.pairs)
    k = 13 * (train.d.shape[2] + 1)
    head, search, net_gap = np.arange(k), np.array([k]), np.array([k + 1])
    inner = np.array([int(f[:8], 16) % 10 == 3 for f in train.family.tolist()])[train.p['deal']]      # a tenth of the training deals
    fit_xtx, fit_xty = train.moments(~inner)
    val_xtx, val_xty = train.moments(inner)
    val_yy, val_n = float((train.y[inner] ** 2).sum()), int(inner.sum())
    scale = float(np.diag(fit_xtx)[:k].mean())
    models = {'zero': (np.zeros(0, int), None), 'search': None, 'search*': (search, None), 'gap head': (net_gap, None),
              'result': (head, head), 'search+res': (np.concatenate([head, search]), head)}
    chosen, weights, inner_mse = {}, {}, {}
    for name, spec in models.items():
        if spec is None:                                    # the search's gap as recorded: slope 1
            w = np.zeros(k + 2)
            w[k] = 1.
            weights[name] = w
            continue
        cols, ridge_on = spec
        best = None
        for c in ((1e-4, 1e-3, 1e-2, 1e-1, 1., 10.) if ridge_on is not None else (0.,)):
            w = solve(fit_xtx, fit_xty, cols, ridge_on if ridge_on is not None else np.zeros(0, int), c * scale) if len(cols) else np.zeros(k + 2)
            mse = (val_yy - 2 * w @ val_xty + w @ val_xtx @ w) / max(val_n, 1)
            if best is None or mse < best[0]:
                best = (mse, c)
        chosen[name], inner_mse[name] = best[1], best[0]
        weights[name] = solve(fit_xtx + val_xtx, fit_xty + val_xty, cols, ridge_on if ridge_on is not None else np.zeros(0, int), best[1] * scale) if len(cols) else np.zeros(k + 2)
    report = dict(net=a.net.name, train_pairs=train.n, train_gap_forks=int((train.p['source'] == 1).sum()), inner_validation_pairs=val_n,
                  ridge={n: c for n, c in chosen.items() if models[n] is not None and models[n][1] is not None},
                  slopes={'search*': float(weights['search*'][k]), 'gap head': float(weights['gap head'][k + 1]), 'search+res': float(weights['search+res'][k])},
                  inner_validation_mse={n: round(float(v), 5) for n, v in inner_mse.items()}, tests=[])
    np.savez(a.out / 'result_head.npz', **{n.replace(' ', '_').replace('*', '_slope').replace('+', '_plus_'): w for n, w in weights.items()})
    seen = np.unique(train.family)
    print(f"training pairs {train.n} ({report['train_gap_forks']} gap forks), ridge {report['ridge']}, slopes {report['slopes']}")
    loaded, offset = [], 0
    for set_path, pairs_path in a.test:
        t = Pairs(params, Path(set_path), Path(pairs_path), drop=seen)
        loaded.append(dict(name=Path(set_path).name, y=t.y, search=t.search, source=t.p['source'], deal=t.p['deal'].astype(np.int64) + offset,
                           pred={n: t.predict(w) for n, w in weights.items()}, dropped=t.dropped))
        offset += len(t.family)
    if len(loaded) > 1:                                     # every unseen pair together
        loaded.append(dict(name='all test sets together', y=np.concatenate([x['y'] for x in loaded]), search=np.concatenate([x['search'] for x in loaded]),
                           source=np.concatenate([x['source'] for x in loaded]), deal=np.concatenate([x['deal'] for x in loaded]),
                           pred={n: np.concatenate([x['pred'][n] for x in loaded]) for n in weights}, dropped=sum(x['dropped'] for x in loaded)))
    for t in loaded:
        pred, y, n_pairs = t['pred'], t['y'], len(t['y'])
        deals, inv = np.unique(t['deal'], return_inverse=True)
        rng = np.random.default_rng(0)
        draws = rng.integers(0, len(deals), (1000, len(deals)))
        entry = dict(set=t['name'], pairs=n_pairs, dropped_as_seen=t['dropped'], deals=len(deals), groups={})
        for label, mask in (('all pairs', np.ones(n_pairs, bool)), ('gap forks', t['source'] == 1), ('audits', t['source'] == 0)):
            if mask.sum() < 20:
                continue
            cnt = np.bincount(inv, mask.astype(float), len(deals))
            def mean_ci(v):
                s = np.bincount(inv, np.where(mask, v, 0.), len(deals))
                b = s[draws].sum(1) / np.maximum(cnt[draws].sum(1), 1)
                return [float(s.sum() / cnt.sum()), float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]
            g = dict(pairs=int(mask.sum()), result_differs=float((y[mask] != 0).mean()), mean_realized_cost=mean_ci(y), mean_search_gap=float(t['search'][mask].mean()), models={})
            base = (pred['search*'] - y) ** 2
            for n, q in pred.items():
                err = (q - y) ** 2
                called = mask & (q < -1e-6)                 # the model says B was the better card
                g['models'][n] = dict(mse=mean_ci(err), mse_minus_search_slope=mean_ci(err - base),
                                      corr=float(np.corrcoef(q[mask], y[mask])[0, 1]) if q[mask].std() > 0 else None,
                                      says_b_better=int(called.sum()), realized_cost_there=float(y[called].mean()) if called.any() else None)
            entry['groups'][label] = g
            print(f"\n== {entry['set']}: {label}: {g['pairs']} pairs, {len(deals)} deals, result differs in {g['result_differs']:.1%}, "
                  f"mean realized cost of B {g['mean_realized_cost'][0]:+.4f} [{g['mean_realized_cost'][1]:+.4f}, {g['mean_realized_cost'][2]:+.4f}], mean search gap {g['mean_search_gap']:.4f}")
            for n, m in g['models'].items():
                corr = '   n/a' if m['corr'] is None else f"{m['corr']:+.3f}"
                called = f"{m['says_b_better']:6d} pairs, realized {m['realized_cost_there']:+.3f}" if m['says_b_better'] else '     0 pairs'
                print(f"  {n:11s} squared error {m['mse'][0]:.4f} | minus search* {m['mse_minus_search_slope'][0]:+.5f} [{m['mse_minus_search_slope'][1]:+.5f}, {m['mse_minus_search_slope'][2]:+.5f}]"
                      f" | corr {corr} | says B better: {called}")
        report['tests'].append(entry)
    (a.out / 'result_head.json').write_text(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
