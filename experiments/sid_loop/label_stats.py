"""Cost and content of a label run, from its sidecar files.

  python label_stats.py LABEL_DIR [--json OUT]

Rows by cards held and role with mean wall time and solver nodes a row, and for each label the share of entries that
are 1, 0 and unasked, by target."""
import json
import sys
from pathlib import Path

import numpy as np


def main():
    d = Path(sys.argv[1])
    files = sorted(f for f in d.glob('*.npz') if not f.name.endswith('.tmp.npz'))
    cost, lab, n_rows = {}, {}, 0
    for f in files:
        with np.load(f) as z:
            held, role, ms, nodes, slots = z['held'], z['role'], z['ms'], z['nodes'], z['slots']
            arrays = {k: z[k] for k in ('guar', 'single', 'cert')}
        n_rows += len(held)
        legal = slots >= 0
        for h in np.unique(held):
            for r in (0, 1):
                m = (held == h) & (role == r)
                if not m.any():
                    continue
                c = cost.setdefault((int(h), r), [0, 0., 0])
                c[0] += int(m.sum()); c[1] += float(ms[m].sum()); c[2] += int(nodes[m].sum())
                for k, x in arrays.items():
                    for t in range(3):
                        v = x[m][:, :, t][legal[m]]
                        e = lab.setdefault((k, r, t), np.zeros(3, np.int64))
                        e += [int((v == 1).sum()), int((v == 0).sum()), int((v < 0).sum())]
    print(f'{len(files)} episodes, {n_rows} rows ({n_rows / max(len(files), 1):.0f} an episode)')
    print('cards role       rows   share  ms/row  nodes/row  core-s')
    total_ms = sum(c[1] for c in cost.values())
    out = dict(episodes=len(files), rows=n_rows, cost={}, labels={})
    for (h, r), (n, ms, nodes) in sorted(cost.items(), reverse=True):
        role = 'declaring' if r == 0 else 'defender'
        print(f'{h:>5} {role:<9} {n:>7} {n / n_rows:>6.1%} {ms / n:>7.2f} {nodes / n:>10.0f} {ms / 1000:>7.1f}')
        out['cost'][f'{h} {role}'] = dict(rows=n, ms_a_row=round(ms / n, 3), nodes_a_row=round(nodes / n, 1))
    print(f'all: {total_ms / n_rows:.2f} ms a row, {total_ms / 1000:.0f} core-seconds')
    out['ms_a_row'] = round(total_ms / n_rows, 3)
    print('label  role      target   share 1  share 0  unasked   entries')
    for (k, r, t), e in sorted(lab.items()):
        if k == 'single' and r == 1:
            continue
        s = e.sum()
        role = 'declaring' if r == 0 else 'defender'
        print(f'{k:<6} {role:<9} {("one down", "contract", "overtrick")[t]:<9} {e[0] / s:>7.1%} {e[1] / s:>8.1%} {e[2] / s:>8.1%} {s:>9}')
        out['labels'][f'{k} {role} {t - 1:+d}'] = dict(one=int(e[0]), zero=int(e[1]), unasked=int(e[2]))
    if '--json' in sys.argv:
        Path(sys.argv[sys.argv.index('--json') + 1]).write_text(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
