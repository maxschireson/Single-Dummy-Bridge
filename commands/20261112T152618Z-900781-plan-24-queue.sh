# boxctl: timeout=300
# boxctl: timeout=120
# plan session: azure2 after match1: the trick 1 to 2 ceiling (slow: about 2.5 hours), then the 64-layout ceiling.
set -uo pipefail
P=$HOME/work/plan
python3 - <<'PY'
import os
p = os.path.expanduser('~/work/plan/queue.txt')
pos = int(open(os.path.expanduser('~/work/plan/queue.pos')).read())
lines = open(p).read().splitlines()
done, waiting = lines[:pos + 1], lines[pos + 1:]
by = {l.split()[0]: l for l in waiting}
new = {'ceilT12': 'ceilT12 $PY scripts/plan_ceiling.py --episodes $P/data/fresh_g6sp --worlds 16 --from-trick 1 --to-trick 2 --skip-files 120 --files 400 --workers 8 --out $R.json'}
order = [n for n in ['ceilT12', 'ceil64b', 'matrix1', 'fam1', 'matrix2'] if n in by or n in new]
out = [new.get(n) or by[n] for n in order]
tmp = p + '.new'
open(tmp, 'w').write('\n'.join(done + out) + '\n')
os.replace(tmp, p)
print('running:', done[-1].split()[0], '| waiting now:', ' '.join(l.split()[0] for l in out))
PY
echo "position $(cat "$P/queue.pos")"; tail -1 "$P/runs/match1.log" | cut -c1-120
