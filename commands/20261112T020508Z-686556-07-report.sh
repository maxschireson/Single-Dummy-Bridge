# boxctl: timeout=300
# Summary of the saved Gen 7 report for the box test.
"$HOME/work/venv/bin/python" - <<'PY'
import json, os
r = json.load(open(os.path.expanduser('~/work/runs/report-01.json')))
def show(k, v, depth=0, limit=1600):
    s = json.dumps(v)
    print(('  ' * depth) + f"{k}: " + (s if len(s) <= limit else s[:limit] + ' ...'))
print('top-level keys:', list(r))
for k, v in r.items():
    if k == 'tree_audit' or k == 'forks':
        continue
    show(k, v)
PY
