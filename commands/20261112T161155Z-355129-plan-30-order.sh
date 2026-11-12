# boxctl: timeout=200
# boxctl: timeout=120
# plan session: azure2 after match1, sized to finish by about 05:00 UTC: tricks 1 to 2, level cards at tricks 3 to 6, 64 layouts.
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
       'ceilTies': 'ceilTies $PY scripts/plan_ceiling.py --episodes $P/data/fresh_g6sp --worlds 16 --ties --bands=-1 --from-trick 3 --to-trick 6 --files 150 --workers 8 --out $R.json',
       'ceil64b': 'ceil64b $PY scripts/plan_ceiling.py --episodes $P/data/fresh_g6sp --worlds 64 --max-gap 0.25 --skip-files 500 --files 300 --workers 8 --out $R.json'}
order = [n for n in ['@source', 'ceilT12', 'ceilTies', 'ceil64b', 'lab1', 'matrix1', 'fam1', 'matrix2'] if n in by or n in new]
out = [new.get(n) or by[n] for n in order]
tmp = p + '.new'
open(tmp, 'w').write('\n'.join(done + out) + '\n')
os.replace(tmp, p)
print('running:', done[-1].split()[0], '| waiting now:', ' '.join(l.split()[0] for l in out))
PY
echo "position $(cat "$P/queue.pos")"; tail -1 "$P/runs/match1.log" | cut -c1-120
