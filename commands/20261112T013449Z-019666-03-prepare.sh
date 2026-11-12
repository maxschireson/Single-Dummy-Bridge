# boxctl: timeout=3600
# Test plan (7s-32 vs 6-32 only), cohort from the capsule, preflight.
set -euo pipefail
cd ~/work/sdb-gen7
PY=~/work/venv/bin/python
RUN=~/work/runs/g7s-vs-g6f-01
mkdir -p ~/work/runs
"$PY" - <<'PYEOF'
import json, os
p = json.load(open('configs/round7-candidate-phase1.json'))
print('audit_references in phase 1 plan:', p['audit_references'])
p['launch_enabled'] = True
p['pending'] = []
p['roster'] = ['7s-32', '6-32']
p['pair_weights'] = {'7s-32~6-32': 1}
p['audit_references'] = {k: v for k, v in p['audit_references'].items() if k in p['roster']}
p['title'] = 'Box test on azure1: 7s-32 (tree path 0.5, 3 tricks) vs 6-32. Local test, not for publication'
json.dump(p, open(os.path.expanduser('~/work/runs/plan-7s-vs-6f.json'), 'w'), indent=1)
print('7s-32 tree:', json.dumps(p['gen7_bots']['7s-32']['gen7']['tree']))
PYEOF
[ -e "$RUN" ] && { echo "$RUN already exists; not overwriting"; exit 1; }
"$PY" ops/prepare_gen7_alpha.py --source ~/work/capsule-gen7-capture/recovery --run "$RUN" --plan ~/work/runs/plan-7s-vs-6f.json | cut -c1-900
echo "== preflight"
start=$(date +%s); "$PY" ops/smoke_gen7.py --run "$RUN" --out ~/work/runs/smoke-01.json 2>&1 | tail -8; echo "preflight took $(( $(date +%s) - start ))s"
"$PY" -c "import json; d=json.load(open('$HOME/work/runs/smoke-01.json')); print(json.dumps(d)[:1500])"
