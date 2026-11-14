# boxctl: timeout=120
# boxctl: timeout=120
# loop session (read-only): the table-net match on azure2 so far.
set -euo pipefail
W=$HOME/work/loop
tail -n 2 "$W/runs.log" | cut -c1-170; echo "loop-rungs: $(systemctl is-active loop-rungs || true); loop-rungs2: $(systemctl is-active loop-rungs2 || true)"
"$W/venv/bin/python" - <<'PY'
import json, os
for run in ('h3-ptb', 'h3-px'):
    f = os.path.expanduser(f'~/work/loop/runs/{run}/results.jsonl')
    if not os.path.exists(f): print(run, 'not started'); continue
    rows = [json.loads(l) for l in open(f) if l.strip()]; v = [r['common'] for r in rows]
    n = len(v); m = sum(v) / max(n, 1); se = (sum((x - m) ** 2 for x in v) / max(n - 1, 1) / max(n, 1)) ** .5
    print(run, 'boards %d: %+.2f +- %.2f IMPs a board for the first-named bot | cpu a board %.0f' % (n, m, se, sum(r['cpu'] for r in rows) / max(n, 1)))
PY
date -u +%FT%TZ
