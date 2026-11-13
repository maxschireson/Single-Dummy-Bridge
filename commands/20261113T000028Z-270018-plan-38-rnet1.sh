# boxctl: timeout=260
# boxctl: timeout=180
# plan session: azure2: pause my own match2 (it resumes from its results afterwards) and build the rollout net v1 first
# (Max, 23:52 UTC): training/rollout-net-v1-20261113/chain.sh, about an hour on the 8 cores.
set -uo pipefail
P=$HOME/work/plan
python3 - <<'PY'
import os
p = os.path.expanduser('~/work/plan/queue.txt')
pos = int(open(os.path.expanduser('~/work/plan/queue.pos')).read())
lines = open(p).read().splitlines()
done, waiting = lines[:pos + 1], lines[pos + 1:]
assert done[-1].split()[0] == 'match2', done[-1][:40]
out = ['@source 343341d357cede0b8c7d8ce9928236212a33e24d', 'rnet1 bash training/rollout-net-v1-20261113/chain.sh', done[-1]] + waiting
tmp = p + '.new'
open(tmp, 'w').write('\n'.join(done + out) + '\n')
os.replace(tmp, p)
print('waiting now:', ' '.join(l.split()[0] for l in out))
PY
pkill -f "pair pr75x-32-v41~7s-32-v41" || echo "nothing to stop"
sleep 50
echo "position $(cat "$P/queue.pos")"; tail -4 "$P/queue.log" | cut -c1-150; wc -l < "$P/runs/match2/results.jsonl"; tail -3 "$P/rnet1/logs/timeline.log" 2>/dev/null
