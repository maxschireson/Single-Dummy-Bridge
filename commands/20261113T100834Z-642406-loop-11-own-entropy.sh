# loop session: how much of the net's log-loss on Stu's cards is Stu's own randomizing? Read-only, on the 200 held-out
# boards of the learning-curve run: the entropy of the probabilities Stu itself played with (the floor for any
# predictor's log-loss) and the mean of its largest probability (the ceiling for exact-card agreement).
set -euo pipefail
W=$HOME/work/loop
nice -n 10 "$W/venv/bin/python" - <<'PY'
import glob, gzip, json, math, os, collections
L = os.path.expanduser('~/work/loop/lc/held')
acc = collections.defaultdict(lambda: [0, 0., 0., 0])
for f in sorted(glob.glob(f'{L}/*.json.gz')):
    d = json.load(gzip.open(f, 'rt'))
    for e in d['unique_tables'].values():
        dec = e['board']['declarer']
        for t in e['tables']:
            for a in t['actions']:
                bp = a.get('behavior_probabilities') or {}
                if len(bp) < 2:
                    continue
                ps = [p for p in bp.values() if p > 0]
                h = -sum(p * math.log(p) for p in ps)
                trick = a['ply'] // 4 + 1
                side = 'declaring' if a['seat'] in (dec, 'NESW'['NESW'.index(dec) ^ 2]) else 'defending'
                mode = (a.get('x8') or {}).get('mode') or ('search' if a.get('estimates') else 'other')
                for k in ('all', 'from trick 7' if trick >= 7 else 'tricks 1-6', side, 'mode ' + mode):
                    v = acc[k]; v[0] += 1; v[1] += h; v[2] += max(ps); v[3] += len(ps) > 1
for k in ('all', 'tricks 1-6', 'from trick 7', 'declaring', 'defending', 'mode search', 'mode blend', 'mode rollout', 'mode claim', 'mode other'):
    n, h, m, mixed = acc[k]
    if n:
        print(f'{k:14} decisions {n:6} | entropy of Stu\'s own probabilities {h / n:.4f} | mean largest probability {m / n:.4f} | decisions with more than one card possible {mixed / n:.3f}')
PY
date -u +%FT%TZ
