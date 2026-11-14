# boxctl: timeout=120
W=$HOME/work/loop
systemctl is-active loop-width loop-pairs; systemctl list-units --no-legend 'loop-*' | cut -c1-100
ls $W/exp-width/w1536/ | head -20
$W/venv/bin/python - $W/exp-width/w1536/metrics.json <<'PY'
import json, sys
m = json.load(open(sys.argv[1]))
print(type(m).__name__, list(m)[:20] if isinstance(m, dict) else len(m))
print(json.dumps(m)[:3000])
PY
tail -5 $W/exp-width/w1536.log | cut -c1-300
pgrep -af "gen8_match|chain.sh" | head -3 | cut -c1-160; tail -3 $W/jobs-azure5.txt 2>/dev/null; ls $W/src/training/rollout-loop-20261113/jobs-azure5*.txt | head
