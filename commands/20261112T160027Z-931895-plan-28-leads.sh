# boxctl: timeout=260
# boxctl: timeout=180
# plan session: azure5: end my own rbc2 (walks; hours longer than I estimated and low value beside the two below), run the
# opening-lead ceiling now, then the second played test; the walks go to the end of the queue in two short parts.
set -uo pipefail
P=$HOME/work/plan
python3 - <<'PY'
import os
p = os.path.expanduser('~/work/plan/queue.txt')
pos = int(open(os.path.expanduser('~/work/plan/queue.pos')).read())
lines = open(p).read().splitlines()
done, waiting = lines[:pos + 1], lines[pos + 1:]
assert done[-1].split()[0] == 'rbc2', done[-1][:40]
by = {l.split()[0]: l for l in waiting}
walk = lambda name, skip: f'{name} $PY scripts/plan_reading_bound.py --episodes $P/data/fresh_g6sp --net models/cardplay/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz --trick 6 --files 8 --skip-files {skip} --chain 400 --chains 2 --workers 8 --out $R.json'
new = {'@source': '@source 1cae1f1584878d66ed7d79edb71d302c4fda0b0b',
       'ceilLead': 'ceilLead $PY scripts/plan_ceiling.py --episodes $P/data/fresh_g6sp --worlds 16 --leads --max-ply 0 --from-trick 1 --to-trick 1 --workers 8 --seconds 16000 --out $R.json',
       'rbc2a': walk('rbc2a', 300), 'rbc2b': walk('rbc2b', 308)}
order = [n for n in ['@source', 'ceilLead', 'match2', 'rbc2a', 'rbc2b', 'rbc1', 'wide3', 'ceil16c'] if n in by or n in new]
out = [new.get(n) or by[n] for n in order]
tmp = p + '.new'
open(tmp, 'w').write('\n'.join(done + out) + '\n')
os.replace(tmp, p)
print('waiting now:', ' '.join(l.split()[0] for l in out))
PY
pkill -f "plan_reading_bound.py --episodes $P/data/fresh_g6sp" || echo "nothing to stop"
sleep 40
echo "position $(cat "$P/queue.pos")"; tail -4 "$P/queue.log" | cut -c1-150; uptime
