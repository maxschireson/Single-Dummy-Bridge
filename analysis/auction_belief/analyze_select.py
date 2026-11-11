import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""Analyse select_layouts.py output: which layouts to solve, scored against held-out posterior layouts."""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from analyze_late import load, mean_se  # noqa: E402

ORDER = ('iid_4', 'iid_8', 'iid_16', 'iid_32', 'iid_64', 'iid_128', 'iid_256', 'sys32', 'top32',
         'med_8', 'med_16', 'med_32', 'med_64', 'strat_8', 'strat_16', 'strat_32', 'strat_64')
SOLVES = dict(iid_4=4, iid_8=8, iid_16=16, iid_32=32, iid_64=64, iid_128=128, iid_256=256, sys32=32, top32=32,
              med_8=8, med_16=16, med_32=32, med_64=64, strat_8=8, strat_16=16, strat_32=32, strat_64=64)


def main(pattern):
    rows = load(pattern)
    dec = []
    for r in rows:
        for d in r['decisions']:
            ref, true = np.array(d['ref']), np.array(d['true_dd'], float)
            row = dict(index=r['index'], trick=d['ply'] // 4 + 1, classes=d['classes'], effective=d['effective'], top=d['top32_mass'])
            for s in ORDER:
                w = np.array(d['picks'][s])
                row[s] = float(ref.max() - w @ ref)
                row['t_' + s] = float(true.max() - w @ true)
            dec.append(row)
    deals = sorted({r['index'] for r in dec})

    def by_deal(key, keep=lambda r: True):
        tot = {i: 0.0 for i in deals}
        for r in dec:
            if keep(r):
                tot[r['index']] += key(r)
        return np.array([tot[i] for i in deals])

    print(f'tables {len(rows)}, decisions {len(dec)} in tricks 1-5; mean seconds per table {np.mean([r["seconds"] for r in rows]):.0f}; '
          f'median classes {np.median([r["classes"] for r in dec]):.0f}, effective {np.median([r["effective"] for r in dec]):.0f}, top-32 mass {np.median([r["top"] for r in dec]):.2f}')
    print('Expected double-dummy loss under the posterior (held-out reference), tricks per table over tricks 1-5.')
    print('"vs iid_32" is paired, positive = better than 32 plain picks. Levels are biased up by the reference maximum; differences are not.')
    print(f'  {"scheme":9s} {"solves":>6} {"loss":>16} {"vs iid_32":>24} {"vs iid_256":>20} {"tricks 1-2 vs iid_32":>22} {"tricks 3-5 vs iid_32":>22} {"true-deal cost":>16}')
    for s in ORDER:
        m, e = mean_se(by_deal(lambda r: r[s]))
        dm, de = mean_se(by_deal(lambda r: r['iid_32'] - r[s]))
        fm, fe = mean_se(by_deal(lambda r: r['iid_256'] - r[s]))
        am, ae = mean_se(by_deal(lambda r: r['iid_32'] - r[s], lambda r: r['trick'] <= 2))
        bm, be = mean_se(by_deal(lambda r: r['iid_32'] - r[s], lambda r: r['trick'] >= 3))
        tm, te = mean_se(by_deal(lambda r: r['t_' + s]))
        z = f'({dm/de:+.1f} SE)' if de > 0 else ''
        print(f'  {s:9s} {SOLVES[s]:6d} {m:7.4f} +-{e:.4f} {dm:+8.4f} +-{de:.4f} {z:>9} {fm:+8.4f} +-{fe:.4f} {am:+9.4f} +-{ae:.4f} {bm:+9.4f} +-{be:.4f} {tm:7.3f} +-{te:.3f}')
    for a, b in (('med_32', 'strat_32'), ('med_32', 'sys32'), ('sys32', 'iid_32'), ('med_16', 'iid_16'), ('med_64', 'iid_64'), ('iid_64', 'iid_32'), ('iid_128', 'iid_32')):
        m, e = mean_se(by_deal(lambda r: r[b] - r[a]))
        print(f'  {a} vs {b}: {m:+.4f} +- {e:.4f} ({m/e:+.1f} SE)')
    print(f'share of decisions where the pick differs in reference value from the 256-layout pick: ' +
          ', '.join(f'{s} {100*np.mean([abs(r[s] - r["iid_256"]) > 1e-9 for r in dec]):.0f}%' for s in ('iid_8', 'iid_32', 'sys32', 'med_32', 'top32', 'iid_128')))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else HERE + '/out/sel_[01].jsonl*')
