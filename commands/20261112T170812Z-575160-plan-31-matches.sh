# boxctl: timeout=200
# boxctl: timeout=120
# plan session: azure2 after match1: the late rule on the Gen 8 prototype's card play (match3, about 4.3 hours), then the
# trick 5 version against Gen 7.1 on match1's deals (match2, about 11 hours). The ceilings move to azure5.
set -uo pipefail
P=$HOME/work/plan
python3 - <<'PY'
import os
p = os.path.expanduser('~/work/plan/queue.txt')
pos = int(open(os.path.expanduser('~/work/plan/queue.pos')).read())
lines = open(p).read().splitlines()
done, waiting = lines[:pos + 1], lines[pos + 1:]
assert done[-1].split()[0] == 'match1', done[-1][:40]
m = lambda name, pair: f'{name} $PY scripts/plan_match.py --source $HOME/work/capsule-gen7-capture/recovery --bots configs/plan-bots.json --pair {pair} --deals 1600 --seed 131 --workers 8 --out $R'
out = ['@source 0f0f4f8', m('match3', 'pr75-8p-32-v41~8p-32-v41'), m('match2', 'pr75x-32-v41~7s-32-v41')]
tmp = p + '.new'
open(tmp, 'w').write('\n'.join(done + out) + '\n')
os.replace(tmp, p)
print('running:', done[-1].split()[0], '| waiting now:', ' '.join(l.split()[0] for l in out))
PY
cd "$P/src" && git fetch -q origin research/plan-leverage-g8-20261112 && git cat-file -t 0f0f4f8 && git log -1 --format='%h %s' 0f0f4f8 | cut -c1-90
echo "position $(cat "$P/queue.pos")"; tail -1 "$P/runs/match1.log" | cut -c1-120
