# boxctl: timeout=200
# boxctl: timeout=200
# plan session: azure2: v1 is done; pause my own match2 again (it resumes from its results afterwards, on the source it
# ran with, 343341d) and run rollout net v2 first (training/rollout-net-v2-20261113/chain.sh at a23f9f9).
set -uo pipefail
P=$HOME/work/plan
python3 - <<'PY'
import os
p = os.path.expanduser('~/work/plan/queue.txt')
pos = int(open(os.path.expanduser('~/work/plan/queue.pos')).read())
lines = open(p).read().splitlines()
done, waiting = lines[:pos + 1], lines[pos + 1:]
assert done[-1].split()[0] == 'match2', done[-1][:60]
assert 'rnet2' not in ' '.join(l.split()[0] for l in lines if l.strip()), 'rnet2 already queued'
out = ['@source a23f9f90955db83ab6fd94dedb80faac269c7e3e', 'rnet2 bash training/rollout-net-v2-20261113/chain.sh',
       '@source 343341d357cede0b8c7d8ce9928236212a33e24d', done[-1]] + waiting
tmp = p + '.new'
open(tmp, 'w').write('\n'.join(done + out) + '\n')
os.replace(tmp, p)
print('waiting now:', ' | '.join(l[:60] for l in out))
PY
pkill -f "pair pr75x-32-v41~7s-32-v41" || echo "nothing to stop"
sleep 60
echo "position $(cat "$P/queue.pos")"; tail -3 "$P/queue.log" | cut -c1-150; wc -l < "$P/runs/match2/results.jsonl"; tail -3 "$P/rnet2/logs/timeline.log" 2>/dev/null | cut -c1-300
