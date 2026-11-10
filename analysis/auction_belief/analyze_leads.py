import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""Analyse lead_ceiling.py output: lead quality by layout set, scored on the true deal."""
import glob
import gzip
import json
import sys

import numpy as np

sys.path.insert(0, RUNTIME)
from bridge_harness.core import Contract, score, imps, vulnerable  # noqa: E402


def load(pattern):
    rows = {}
    for f in sorted(glob.glob(pattern)):
        for line in (gzip.open(f, 'rt') if f.endswith('.gz') else open(f)):
            try:
                r = json.loads(line)
            except Exception:
                continue
            rows[r['index']] = r
    return [rows[k] for k in sorted(rows)]


def pick(dd):
    """PIMC choice: uniform over leads whose mean value ties the best. Returns weights."""
    m = dd.mean(axis=0)
    best = np.isclose(m, m.max(), atol=1e-9)
    return best / best.sum()


def subsets(n, size):
    return [np.arange(i, i + size) for i in range(0, n - size + 1, size)]


def analyse(rows, exclude_capped=False, quiet=False):
    arms = [('exact', 32), ('exact', 64), ('belief', 32), ('belief', 64), ('belief', 128), ('uniform', 32)]
    cost = {a: [] for a in arms}
    weights = {a: [] for a in arms}
    meta = []
    for r in rows:
        if r.get('passed_out'):
            continue
        if exclude_capped and r['exact_stats']['capped']:
            continue
        if len(r['exact_dd']) < 64:
            continue
        true = np.array(r['true_dd'], float)
        c = Contract.parse(r['contract'], r['declarer'])
        vul = vulnerable(r['vulnerability'], c.declarer)
        dscore = np.array([score(c, int(13 - t), vul) for t in true], float)
        row_w = {}
        for name, size in arms:
            dd = np.array(r[name + '_dd'], float)
            ws = [pick(dd[ix]) for ix in subsets(len(dd), size)]
            row_w[(name, size)] = ws
            cost[(name, size)].append(np.mean([true.max() - w @ true for w in ws]))
        meta.append(dict(r=r, true=true, dscore=dscore, w=row_w))
    n = len(meta)
    res = dict(n=n)

    def mean_se(x):
        x = np.asarray(x, float)
        return x.mean(), x.std(ddof=1) / np.sqrt(len(x))

    def imp_diff(m, a, b):
        """Expected IMPs to arm a over arm b on the true deal (declarer score lower is better for the leader)."""
        tot = []
        for wa in m['w'][a]:
            for wb in m['w'][b]:
                ia, ib = np.flatnonzero(wa), np.flatnonzero(wb)
                v = 0.
                for i in ia:
                    for j in ib:
                        v += wa[i] * wb[j] * imps(m['dscore'][j] - m['dscore'][i])
                tot.append(v)
        return float(np.mean(tot))

    out = []
    out.append(f'leads {n}' + (' (capped leads excluded)' if exclude_capped else ''))
    out.append('Double-dummy cost of the chosen lead on the true deal, tricks (lower is better)')
    for a in arms:
        m, s = mean_se(cost[a])
        res[f'cost_{a[0]}{a[1]}'] = (m, s)
        out.append(f'  {a[0]:8s}{a[1]:4d}: {m:.4f} +- {s:.4f}')
    pairs = [(('exact', 32), ('belief', 32)), (('exact', 64), ('belief', 64)), (('exact', 32), ('belief', 64)),
             (('exact', 32), ('belief', 128)), (('exact', 64), ('belief', 128)),
             (('belief', 32), ('uniform', 32)), (('exact', 32), ('uniform', 32)),
             (('belief', 64), ('belief', 32)), (('belief', 128), ('belief', 32)), (('exact', 64), ('exact', 32))]
    out.append('Paired differences, first minus second: tricks gained per lead (positive favours first), and IMPs per lead')
    for a, b in pairs:
        d = np.array(cost[b]) - np.array(cost[a])
        m, s = mean_se(d)
        im = np.array([imp_diff(x, a, b) for x in meta])
        mi, si = mean_se(im)
        res[f'{a[0]}{a[1]}_vs_{b[0]}{b[1]}'] = dict(tricks=(m, s), imps=(mi, si))
        out.append(f'  {a[0]}{a[1]} vs {b[0]}{b[1]}: {m:+.4f} +- {s:.4f} tricks ({m/s:+.1f} SE); {mi:+.3f} +- {si:.3f} IMPs')
    # diagnostics
    cons = [np.mean(m['r']['belief_consistent']) for m in meta]
    ucons = [np.mean(m['r']['uniform_consistent']) for m in meta]
    econs = [np.mean(m['r']['exact_consistent']) for m in meta]
    out.append(f'Share of layouts consistent with the auction: belief {np.mean(cons)*100:.2f}% (median {np.median(cons)*100:.2f}%), '
               f'uniform {np.mean(ucons)*100:.2f}%, exact {np.mean(econs)*100:.1f}%')

    def errors(name):
        hcp, ln = [], []
        for m in meta:
            t = np.array(m['r']['true_summary'])
            s = np.array(m['r'][name + '_summary'])
            if not len(s):
                continue
            hcp.append(np.abs(s[:, :, 0] - t[None, :, 0]).sum(1).mean())
            ln.append(np.abs(s[:, :, 1:] - t[None, :, 1:]).sum((1, 2)).mean())
        return np.mean(hcp), np.mean(ln)
    for name in ('uniform', 'belief', 'exact'):
        h, l = errors(name)
        res[f'err_{name}'] = (h, l)
        out.append(f'  {name:8s} summed HCP error {h:.2f}, summed suit-length error {l:.2f}')
    st = [m['r']['exact_stats'] for m in meta]
    capped = np.mean([s['capped'] for s in st])
    acc = np.array([s['pilot_accept'] for s in st])
    out.append(f'Exact sampler: capped {capped*100:.1f}% of leads; later rounds used in {np.mean([s["rounds"]>0 for s in st])*100:.0f}%; '
               f'mean distinct block hands {np.mean([s["distinct_blocks"] for s in st]):.1f} of 64; '
               f'median checks {np.median([s["checks"] for s in st]):.0f}; true layout consistent in {np.mean([all(m["r"]["true_consistent"]) for m in meta])*100:.1f}%')
    secs = [m['r']['seconds'] for m in meta]
    out.append(f'Seconds per lead: exact sampling mean {np.mean([s["exact"] for s in secs]):.1f} (median {np.median([s["exact"] for s in secs]):.1f}), solver {np.mean([s["dds"] for s in secs]):.1f}')
    # agreement
    agree = np.mean([float(m['w'][('exact', 32)][0] @ m['w'][('belief', 32)][0] > 0) for m in meta])
    out.append(f'Exact-32 and belief-32 share a best lead on {agree*100:.0f}% of leads')
    if not quiet:
        print('\n'.join(out))
    return res, meta


if __name__ == '__main__':
    rows = load(sys.argv[1] if len(sys.argv) > 1 else HERE + '/out/main_*.jsonl*')
    analyse(rows)
    if any(r.get('exact_stats', {}).get('capped') for r in rows):
        print()
        analyse(rows, exclude_capped=True)
