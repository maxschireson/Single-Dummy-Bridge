#!/usr/bin/env python3
"""Report on a gen7_bench rows file: each tree against PIMC on the same layouts, the share of its
correction that shows up in real play, and (optionally) the same pairs in another rows file.

  python scripts/gen7_bench_report.py ROWS.json [OTHER.json]
"""
import json
import math
import sys

import numpy as np


def clustered(x, fam):
    by = {}
    for v, k in zip(x, fam):
        by.setdefault(k, []).append(v)
    totals, counts = np.array([sum(v) for v in by.values()]), np.array([len(v) for v in by.values()])
    mean = totals.sum() / counts.sum()
    se = math.sqrt(((totals - mean * counts) ** 2).sum() * len(by) / max(1, len(by) - 1)) / counts.sum()
    return float(mean), float(se)


def weight(f, pimc, corr, fam, boots=300):
    """Coefficient of the correction when realized cost is regressed on PIMC's gap and the correction."""
    X = np.column_stack([np.ones(len(f)), pimc, corr])
    beta = np.linalg.lstsq(X, f, rcond=None)[0]
    fams = sorted(set(fam))
    idx = {k: np.flatnonzero(fam == k) for k in fams}
    rng = np.random.default_rng(0)
    got = []
    for _ in range(boots):
        pick = np.concatenate([idx[k] for k in rng.choice(fams, len(fams))])
        got.append(np.linalg.lstsq(X[pick], f[pick], rcond=None)[0][2])
    return float(beta[2]), float(np.std(got))


def report(rows, title):
    f = np.array([r['final'] for r in rows], float)
    fam = np.array([r['family'] for r in rows])
    pimc = np.array([r['pimc'] for r in rows])
    pk = np.array([r['pimc_k'] for r in rows])
    names = sorted(k for k in rows[0] if k.startswith('tree_'))
    print(f"\n== {title}: {len(rows)} pairs, {len(set(fam))} deals; realized cost of B {f.mean():.3f}; B better {np.mean(f < 0):.3f}")
    base = np.where(pk < -1e-9, -f, 0.)
    big = np.where(pimc < -1e-9, -f, 0.)
    m, s = clustered(big, fam)
    print(f"   fresh 32-layout PIMC over Gen 6 {m:+.4f} +- {s:.4f}")
    for n in names:
        t = np.array([r[n] for r in rows])
        tag = n[5:]
        gain = np.where(t < -1e-9, -f, 0.)
        m1, s1 = clustered(gain - base, fam)
        mix = pimc + t - pk
        m2, s2 = clustered(np.where(mix < -1e-9, -f, 0.) - big, fam)
        corr = t - pk
        w, ws = weight(f, pimc, corr, fam) if len(set(fam)) > 20 else (float('nan'), float('nan'))
        sec = np.mean([r.get(f'seconds_{tag}', float('nan')) for r in rows])
        print(f"   {n:40s} vs PIMC same layouts {m1:+.4f} +- {s1:.4f} | as correction to 32-layout PIMC {m2:+.4f} +- {s2:.4f} | "
              f"prefers B {np.mean(t < -1e-9):.3f} (PIMC {np.mean(pk < -1e-9):.3f}) | correction sd {corr.std():.3f} zero {np.mean(np.abs(corr) < 1e-9):.2f} "
              f"weight {w:+.3f} +- {ws:.3f} | {sec:.2f} s")


def main():
    d = json.load(open(sys.argv[1]))
    rows = d['rows']
    print('settings', {k: v for k, v in d['settings'].items()})
    report(rows, 'ALL')
    for b in sorted({r['band'] for r in rows}):
        sub = [r for r in rows if r['band'] == b]
        if len(sub) >= 40:
            report(sub, f'band {b}')
    for ph in sorted({r['phase'] for r in rows}):
        sub = [r for r in rows if r['phase'] == ph]
        if len(sub) >= 40:
            report(sub, f'phase {ph}')
    if len(sys.argv) > 2:
        other = json.load(open(sys.argv[2]))['rows']
        key = lambda r: (r['family'], r['ply'], r['band'], round(r['estimated'], 6), round(r['pimc'], 6))
        index = {key(r): r for r in other}
        both = [(r, index[key(r)]) for r in rows if key(r) in index]
        print(f"\n== same pairs in {sys.argv[2]}: {len(both)} of {len(rows)}")
        if both:
            merged = []
            for r, o in both:
                m = dict(r)
                for k, v in o.items():
                    if k.startswith('tree_') or k.startswith('seconds_'):
                        m.setdefault(k if k not in r else k + '_other', v)
                merged.append(m)
            report(merged, 'JOINED')
            f = np.array([m['final'] for m in merged], float)
            fam = np.array([m['family'] for m in merged])
            names = sorted(k for k in merged[0] if k.startswith('tree_'))
            g = {n: np.where(np.array([m[n] for m in merged]) < -1e-9, -f, 0.) for n in names}
            for i, a in enumerate(names):
                for b in names[i + 1:]:
                    mm, ss = clustered(g[a] - g[b], fam)
                    print(f"   {a} minus {b}: {mm:+.4f} +- {ss:.4f}")


if __name__ == '__main__':
    main()
