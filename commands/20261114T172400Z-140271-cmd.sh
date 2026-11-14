# boxctl: timeout=480
# loop session (Max, 17:11 UTC: other rollout mechanisms?): the same read-only check of the rollouts' values against the
# tables' results on this box's self-play records (bench/value_check.py, sent inline). Two workers at low priority.
set -euo pipefail
W=$HOME/work/loop
cat > /tmp/value_check.py <<'PYEOF'
#!/usr/bin/env python3
"""Are the rollouts' values right in level? What the rollouts expected of the card played against what the table took.

  python training/rollout-loop-20261113/bench/value_check.py EPISODES_DIR [EPISODES_DIR ...] [--boards N] [--workers K] [--bot ID]

For every rollout decision of the recorded tables (level 2 capture: every layout's result for every candidate): declarer's
tricks the rollouts expected with the card played, and the chance they gave the contract, against declarer's tricks at
that table. By what the seat was doing (declaring, defending, the opening lead) and by trick; the contract's chance also
as a calibration table. Standard errors by table (a table's decisions share its result).

The rollouts finish every layout with the net's card in all four seats; the table is finished by the bot and its real
opponents. A gap between the two is the LEVEL error of the values at that stage (the net's play standing in for the
players', and the layouts' weights). It does not say whether the ORDER of the candidates is right: an error common to
every candidate changes no choice. The card played is the best of up to four means on shared layouts, which flatters
its own side by a little (about the standard error of a deficit, a few hundredths of a trick).

Needs numpy only; reads the records as written (no engine).
"""
import argparse
import base64
from collections import defaultdict
import glob
import gzip
import json
import math
from multiprocessing import Pool
from pathlib import Path

import numpy as np

STAGES = (('trick 1', 1, 1), ('trick 2', 2, 2), ('tricks 3-4', 3, 4), ('tricks 5-8', 5, 8), ('tricks 9-13', 9, 13))
BINS = (0., .05, .2, .4, .6, .8, .95, 1.0000001)


def stage(trick):
    return next(name for name, lo, hi in STAGES if lo <= trick <= hi)


def side(seat):
    return ('NESW'.index(seat) if isinstance(seat, str) else int(seat)) % 2


def one_file(args):
    path, bot = args
    d = json.load(gzip.open(path, 'rt'))
    out = []
    for key, e in d['unique_tables'].items():
        if e.get('schema_version') == 'v4-passed-out-v1' or not e.get('tables'):
            continue
        board = e['board']
        target = int(board['contract'][0]) + 6
        dec = side(board['declarer'])
        for k, table in enumerate(e['tables']):
            if table.get('depth', 0) or table.get('fork_kind') or table.get('declarer_tricks') is None:
                continue
            actual = int(table['declarer_tricks'])
            for a in table['actions']:
                note = a.get('x8') or {}
                if note.get('mode') != 'rollout' or len(note.get('cards') or ()) < 2 or 'cap' not in note or 'chosen' not in note:
                    continue
                if bot and d.get(a.get('player') or '') != bot:
                    continue
                j = next((i for i, run in enumerate(note['runs']) if note['chosen'] in run), None)
                if j is None:
                    continue
                cap = note['cap']
                shape = tuple(cap['shape'])
                w = np.frombuffer(base64.b64decode(cap['w']), np.float32).astype(np.float64)
                t = np.frombuffer(base64.b64decode(cap['t']), np.int8).reshape(shape).astype(np.int64)
                f = np.frombuffer(base64.b64decode(cap['f']), np.uint8).reshape(shape).astype(bool)
                played = t[:, j] >= 0
                if not played.any():
                    continue
                final = np.where(f[:, j], np.maximum(t[:, j], target), t[:, j])[played]
                ww = w[played] / w[played].sum()
                declaring = side(a['seat']) == dec
                role = 'lead' if note.get('lead') or a.get('ply') == 0 else 'declaring' if declaring else 'defending'
                out.append((f'{path}|{key}|{k}', d.get(a.get('player') or '', '?'), role, stage(int(note['trick'])),
                            float(ww @ final), float(ww @ (final >= target)), actual, int(actual >= target), int(played.sum())))
    return out


def clustered(rows):
    """(mean, standard error by table, decisions, tables) of (table, value) pairs."""
    by = defaultdict(lambda: [0., 0])
    for table, v in rows:
        by[table][0] += v
        by[table][1] += 1
    n, g = sum(c for _, c in by.values()), len(by)
    if not n:
        return float('nan'), float('nan'), 0, 0
    m = sum(s for s, _ in by.values()) / n
    se = math.sqrt(sum((s - m * c) ** 2 for s, c in by.values()) * g / max(g - 1, 1)) / n
    return m, se, n, g


def main():
    p = argparse.ArgumentParser()
    p.add_argument('episodes', type=Path, nargs='+')
    p.add_argument('--boards', type=int, default=0, help='at most this many record files a folder (0 = all)')
    p.add_argument('--workers', type=int, default=2)
    p.add_argument('--bot', default='', help='only this bot id\'s decisions')
    a = p.parse_args()
    files = []
    for folder in a.episodes:
        found = sorted(glob.glob(str(folder / '*.json.gz')))
        files += found[:a.boards] if a.boards else found
    rows = []
    with Pool(a.workers) as pool:
        for part in pool.imap_unordered(one_file, [(f, a.bot) for f in files], chunksize=8):
            rows += part
    bots = sorted({r[1] for r in rows})
    print(f'{len(files)} record files; {len(rows)} rollout decisions with their layouts kept; bots {bots}')
    print("Declarer's tricks: the rollouts' mean for the card played minus the table's result (+: the rollouts expected declarer to take more)")
    print("Contract: the rollouts' chance of making minus the share made")
    for bot in bots:
        print(f'\n{bot}')
        print(f'  {"deciding":9s} {"stage":11s} {"decisions":>9s} {"tables":>6s} | {"expected":>8s} {"took":>6s} {"difference":>16s} | {"chance":>6s} {"made":>6s} {"difference":>16s}')
        for role in ('lead', 'declaring', 'defending'):
            for st in [s[0] for s in STAGES] + ['all']:
                sel = [r for r in rows if r[1] == bot and r[2] == role and (st == 'all' or r[3] == st)]
                if not sel:
                    continue
                m, se, n, g = clustered([(r[0], r[4] - r[6]) for r in sel])
                pm, pse, _, _ = clustered([(r[0], r[5] - r[7]) for r in sel])
                print(f'  {role:9s} {st:11s} {n:9d} {g:6d} | {np.mean([r[4] for r in sel]):8.3f} {np.mean([r[6] for r in sel]):6.3f} {m:+8.3f} +- {se:.3f} |'
                      f' {np.mean([r[5] for r in sel]):6.3f} {np.mean([r[7] for r in sel]):6.3f} {pm:+8.3f} +- {pse:.3f}')
        print("  calibration of the contract's chance (the rollouts' chance for the card played, in bins: decisions, mean chance, share made +- SE by table)")
        for role in ('declaring', 'defending'):
            for early, name in ((True, 'tricks 1-4'), (False, 'tricks 5-13')):
                parts = []
                for lo, hi in zip(BINS[:-1], BINS[1:]):
                    sel = [r for r in rows if r[1] == bot and r[2] == role and lo <= r[5] < hi and (r[3] in ('trick 1', 'trick 2', 'tricks 3-4')) == early]
                    if len(sel) < 20:
                        continue
                    m, se, n, g = clustered([(r[0], float(r[7])) for r in sel])
                    parts.append(f'{np.mean([r[5] for r in sel]):.2f}->{m:.2f}+-{se:.2f} ({n})')
                print(f'    {role:9s} {name:11s} ' + ' | '.join(parts))


if __name__ == '__main__':
    main()
PYEOF
cd "$W"
for r in sp3s sps0; do
  [ -d runs/$r/episodes ] || continue
  echo "=== $r: $(python3 -c "import json;m=json.load(open('runs/$r/manifest.json'));print(m.get('candidate'), m.get('opponent'))" 2>/dev/null || true)"
  nice -n 10 "$W/venv/bin/python" /tmp/value_check.py runs/$r/episodes --workers 2 --boards 2500
done
date -u +%T
