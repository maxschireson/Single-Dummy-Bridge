# boxctl: timeout=200
# boxctl: timeout=120
# plan session: azure2 after match1: the opening-lead ceiling first (about 4.7 hours), then tricks 1 to 2, level cards, labels.
set -uo pipefail
P=$HOME/work/plan
python3 - <<'PY'
import os
p = os.path.expanduser('~/work/plan/queue.txt')
pos = int(open(os.path.expanduser('~/work/plan/queue.pos')).read())
lines = open(p).read().splitlines()
done, waiting = lines[:pos + 1], lines[pos + 1:]
by = {l.split()[0]: l for l in waiting}
new = {'@source': '@source 1cae1f1584878d66ed7d79edb71d302c4fda0b0b',
       'ceilLead': 'ceilLead $PY scripts/plan_ceiling.py --episodes $P/data/fresh_g6sp --worlds 16 --leads --max-ply 0 --from-trick 1 --to-trick 1 --workers 8 --seconds 17000 --out $R.json'}
order = [n for n in ['@source', 'ceilLead', 'ceilT12', 'ceilTies', 'lab1', 'ceil64b', 'matrix1', 'fam1', 'matrix2'] if n in by or n in new]
out = [new.get(n) or by[n] for n in order]
tmp = p + '.new'
open(tmp, 'w').write('\n'.join(done + out) + '\n')
os.replace(tmp, p)
print('running:', done[-1].split()[0], '| waiting now:', ' '.join(l.split()[0] for l in out))
PY
echo "position $(cat "$P/queue.pos")"; tail -1 "$P/runs/match1.log" | cut -c1-120
