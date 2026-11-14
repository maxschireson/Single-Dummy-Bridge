# boxctl: timeout=120
# boxctl: timeout=120
# loop session (read-only): how long the BEN (200) matches took on azure3, and the state of its units.
set -euo pipefail
W=$HOME/work/loop
grep -E "ps200|bg-200|bb-200|BEN \(200\)|ben4|ben3" "$W/runs.log" | cut -c1-150 | tail -n 44 | awk 'NR<=6 || /start b[03]-ps200-1 |end b[03]-ps200-8|servers|ended/'
echo "units: rungs $(systemctl is-active loop-rungs || true) rungs2 $(systemctl is-active loop-rungs2 || true) bensession $(systemctl is-active loop-bensession || true) chain $(systemctl is-active loop-chain || true)"
for n in 1 2 3 4 5 6 7 8; do printf '%s ' "$(systemctl is-active ben-server@$n || true)"; done; echo
"$W/venv/bin/python" - <<'PY'
import json, glob, os
for run in ('b0-ps200', 'b3-ps200'):
    rows = [json.loads(l) for f in sorted(glob.glob(os.path.expanduser(f'~/work/loop/runs/{run}-*/results.jsonl'))) for l in open(f) if l.strip()]
    if rows:
        print(run, 'boards', len(rows), 'cpu a board %.0f' % (sum(r['cpu'] for r in rows) / len(rows)), 'seconds a board %.0f' % (sum(r.get('seconds', 0) for r in rows) / len(rows)), sorted(rows[0])[:14])
PY
free -g | sed -n 2p; date -u +%FT%TZ
