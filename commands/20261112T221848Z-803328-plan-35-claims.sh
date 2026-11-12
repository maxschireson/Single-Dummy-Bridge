# boxctl: timeout=260
# boxctl: timeout=180
# plan session: azure5: end my own rbc2a (walks, low value) and run two played tests on match1's deals now:
# match4 = prc-32-v41 (late self-simulation with the claim finder) against 7s-32-v41; match5 = cl-32-v41 (the claim
# finder alone) against 7s-32-v41. The walks go back on after them.
set -uo pipefail
P=$HOME/work/plan
python3 - <<'PY'
import os
p = os.path.expanduser('~/work/plan/queue.txt')
pos = int(open(os.path.expanduser('~/work/plan/queue.pos')).read())
lines = open(p).read().splitlines()
done, waiting = lines[:pos + 1], lines[pos + 1:]
assert done[-1].split()[0] == 'rbc2a', done[-1][:40]
rbc2a = done[-1]
m = lambda name, pair: f'{name} SURE_BIN=$P/bin/sure_cpp PYTHONPATH=$P/pylib $PY scripts/plan_match.py --source $P/capsule/recovery --bots configs/plan-bots.json --pair {pair} --deals 1600 --seed 131 --workers 8 --out $R'
out = ['@source 0d1db2bb9944abc83f0bc6de64d2e47299c2bf44', m('match4', 'prc-32-v41~7s-32-v41'), m('match5', 'cl-32-v41~7s-32-v41'), rbc2a] + waiting
tmp = p + '.new'
open(tmp, 'w').write('\n'.join(done + out) + '\n')
os.replace(tmp, p)
print('waiting now:', ' '.join(l.split()[0] for l in out))
PY
pkill -f "plan_reading_bound.py --episodes $P/data/fresh_g6sp" || echo "nothing to stop"
sleep 60
echo "position $(cat "$P/queue.pos")"; tail -3 "$P/queue.log" | cut -c1-160; tail -2 "$P/runs/match4.log" 2>/dev/null | cut -c1-200; ls "$P/bin"; uptime
