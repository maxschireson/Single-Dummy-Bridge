# boxctl: timeout=120
# boxctl: timeout=120
# loop session (read-only): the base spec's near_tie and exploration, for the Gen 8 personalities.
W=$HOME/work/loop
$W/venv/bin/python -c "
import json; m=json.load(open('$W/capsule/recovery/manifest.json'))
for k in ('6-32','3'):
    s=m['bots'][k]; print(k, {x: s.get(x) for x in ('near_tie','exploration','samples','engine','policy_role')})"
tail -n 1 $W/runs.log | cut -c1-120; echo "h3-p2 boards: $(wc -l < $W/runs/h3-p2/results.jsonl)"
