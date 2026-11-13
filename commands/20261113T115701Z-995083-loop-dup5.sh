# boxctl: timeout=300
# boxctl: timeout=300
# loop session: are the two tables of a self-play board the same play? (read-only)
W=$HOME/work/loop
"$W/venv/bin/python" - <<'PY'
import glob, gzip, json, os
W = os.path.expanduser('~/work/loop/runs')
for run in ('s0', 'r0'):
    files = sorted(glob.glob(f'{W}/{run}/episodes/*'))[:120]
    same = n = 0; first = []
    for f in files:
        d = json.load(gzip.open(f, 'rt'))
        t = [[a['card'] for a in e['tables'][0]['actions']] for e in d['unique_tables'].values() if e.get('tables') and e['tables'][0]['actions']]
        if len(t) != 2: continue
        n += 1
        if t[0] == t[1]: same += 1
        else: first.append(next(i for i, (x, y) in enumerate(zip(t[0], t[1])) if x != y))
    print(run, 'boards with two tables', n, '| identical card for card', same, '| first differing ply where they differ', sorted(first)[:12])
PY
tail -n 2 "$W/runs.log" | cut -c1-150; wc -l < "$W/runs/l0b-p/results.jsonl"; df -h "$W" | tail -1; date -u +%FT%TZ
