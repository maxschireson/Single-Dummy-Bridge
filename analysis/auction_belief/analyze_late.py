import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""Analyse late_play.py output: decision quality by layout source, scored on the true deal."""
import glob
import gzip
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nbid  # noqa: F401,E402  (puts the runtime on the path)
from bridge_harness.core import Board, Game, Contract, card, score, imps, vulnerable  # noqa: E402

ROOT = FEED
ARMS = ('v5', 'uniform', 'list', 'list32')


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


def declarer_tricks_by_ply(index):
    ep = json.load(gzip.open(f'{ROOT}/episodes/{index:06d}.json.gz'))
    t = ep['unique_tables'][ep['regimes']['common']['tables'][0]]
    game = Game(Board.from_dict(t['board']))
    out = []
    for act in t['tables'][0]['actions']:
        out.append(game.declarer_tricks)
        game.play(card(act['card']))
    return out


def mean_se(x):
    x = np.asarray(x, float)
    return x.mean(), (x.std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else float('nan'))


def main(pattern):
    rows = load(pattern)
    per_dec = []          # one row per decision
    for r in rows:
        c = Contract.parse(r['contract'], r['declarer'])
        vul = vulnerable(r['vulnerability'], c.declarer)
        sc = np.array([score(c, t, vul) for t in range(14)], float)
        decl = declarer_tricks_by_ply(r['index'])
        plies = {p['ply']: p for p in r['plies']}
        for d in r['decisions']:
            p = plies[d['ply']]
            true = np.array(p['true_dd'], float)
            declaring = p['actor'] % 2 == c.declarer % 2
            rem = 13 - d['ply'] // 4
            total = decl[d['ply']] + (true if declaring else rem - true)          # declarer's final tricks per card
            s = sc[total.astype(int)] * (1 if declaring else -1)                  # score from the actor's side
            row = dict(index=r['index'], ply=d['ply'], trick=d['ply'] // 4 + 1, declaring=declaring,
                       n_list=d['n_list'], n_solved=d['n_solved'], n_legal=len(true))
            for a in ARMS:
                w = np.array(d[a])
                row['cost_' + a] = float(true.max() - w @ true)
            for a, b in (('list', 'v5'), ('list32', 'v5'), ('v5', 'uniform'), ('list', 'uniform'), ('list', 'list32')):
                wa, wb = np.array(d[a]), np.array(d[b])
                row[f'imp_{a}_{b}'] = float(sum(wa[i] * wb[j] * imps(s[i] - s[j]) for i in np.flatnonzero(wa) for j in np.flatnonzero(wb)))
            played = p['legal'].index(p['played'])
            row['cost_actual'] = float(true.max() - true[played])
            per_dec.append(row)
    deals = sorted({r['index'] for r in per_dec})
    print(f'tables {len(rows)}, late decisions {len(per_dec)} ({len(per_dec)/max(len(rows),1):.1f} per table)')

    def by_deal(key, keep=lambda r: True):
        tot = {i: 0.0 for i in deals}
        n = 0
        for r in per_dec:
            if keep(r):
                tot[r['index']] += key(r); n += 1
        return np.array([tot[i] for i in deals]), n

    print('Double-dummy cost on the true deal, tricks per table over tricks 6-12 (lower is better), SE across tables')
    for a in ARMS + ('actual',):
        v, n = by_deal(lambda r: r['cost_' + a])
        m, s = mean_se(v)
        print(f'  {a:8s} {m:.4f} +- {s:.4f}   ({m * len(deals) / n:.4f} per decision)')
    print('Paired, first minus second: tricks gained per table, per decision, and IMPs per table (positive favours first)')
    for a, b in (('list', 'v5'), ('list32', 'v5'), ('list', 'list32'), ('v5', 'uniform'), ('list', 'uniform')):
        v, n = by_deal(lambda r: r['cost_' + b] - r['cost_' + a])
        m, s = mean_se(v)
        vi, _ = by_deal(lambda r: r[f'imp_{a}_{b}'])
        mi, si = mean_se(vi)
        print(f'  {a:7s} vs {b:7s}: {m:+.4f} +- {s:.4f} tricks/table ({m/s:+.1f} SE); {m*len(deals)/n:+.5f} per decision; {mi:+.3f} +- {si:.3f} IMPs/table')
    print('list vs v5 by trick (tricks gained per table at that trick), with median list size')
    for t in range(6, 13):
        v, n = by_deal(lambda r: r['cost_v5'] - r['cost_list'], lambda r: r['trick'] == t)
        m, s = mean_se(v)
        sizes = [r['n_list'] for r in per_dec if r['trick'] == t]
        full = np.mean([r['n_list'] == r['n_solved'] for r in per_dec if r['trick'] == t])
        print(f'  trick {t:2d}: {m:+.4f} +- {s:.4f}   decisions {n:5d}   median list {np.median(sizes):6.0f}   fully solved {100*full:3.0f}%')
    for name, keep in (('declarer side', lambda r: r['declaring']), ('defenders', lambda r: not r['declaring'])):
        v, n = by_deal(lambda r: r['cost_v5'] - r['cost_list'], keep)
        m, s = mean_se(v)
        print(f'  {name:14s}: list vs v5 {m:+.4f} +- {s:.4f} tricks/table over {n} decisions')
    differ = np.mean([abs(r['cost_v5'] - r['cost_list']) > 1e-9 for r in per_dec])
    print(f'decisions where list and v5 differ in true double-dummy value: {100*differ:.1f}%')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else HERE + '/out/late_*.jsonl*')
