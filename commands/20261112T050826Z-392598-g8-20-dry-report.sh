# boxctl: timeout=120
# boxctl: timeout=120
# g8: the top of the dry run's preflight report.
set -uo pipefail
"$HOME/work/venv/bin/python" - "$HOME/work/g8/runs/arena-dry-smoke" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
def short(v, depth=0):
    if isinstance(v, dict) and depth < 2:
        return {k: short(x, depth + 1) for k, x in list(v.items())[:14]}
    s = json.dumps(v)
    return s if len(s) < 160 else s[:160] + '...'
for k, v in r.items():
    print(k, ':', json.dumps(short(v))[:700])
PY
