# boxctl: timeout=120
# boxctl: timeout=120
# loop session (read-only): the gate's first block on azure3.
set -euo pipefail
W=$HOME/work/loop
tail -n 3 "$W/runs.log" | cut -c1-170
"$W/venv/bin/python" - <<'PY'
import json, glob, os
R = {}
for run in ('b3-pst200', 'b3-ps200', 'b0-ps200', 'bg-200', 'b3-pst200b'):
    rows = {}
    for f in sorted(glob.glob(os.path.expanduser(f'~/work/loop/runs/{run}-[1-8]/results.jsonl'))):
        for l in open(f):
            if l.strip():
                r = json.loads(l); rows[r['index']] = r['common']
    R[run] = rows
def st(v):
    n = len(v)
    if n < 2: return 'n=%d' % n
    m = sum(v) / n; se = (sum((x - m) ** 2 for x in v) / (n - 1) / n) ** .5
    return '%+.2f +- %.2f (%d)' % (m, se, n)
for k, v in R.items(): print(k, st(list(v.values())))
for a, b in (('b3-pst200', 'b3-ps200'), ('b3-pst200', 'b0-ps200'), ('b3-pst200', 'bg-200')):
    both = sorted(set(R[a]) & set(R[b])); print('by deal', a, 'minus', b, st([R[a][i] - R[b][i] for i in both]))
PY
date -u +%FT%TZ
