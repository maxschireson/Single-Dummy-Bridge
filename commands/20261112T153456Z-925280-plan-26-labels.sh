# boxctl: timeout=1000
# boxctl: timeout=900
# plan session: the earlier 5,214 boards of the 6-32 self-play feed onto azure2 (git fetch only; light), for a set of
# played-out labels tonight. Then the queue after match1: level-card ceiling, the labels, tricks 1 to 2, 64 layouts.
set -uo pipefail
P=$HOME/work/plan; PY=$HOME/work/venv/bin/python
cd "$P/src"
"$PY" scripts/plan_fetch.py --branch arena-gen6-fast-selfplay-20261111-19bbdce5-feed --first 0 --last 5213 --out "$P/data/g6sp_train" 2>&1 | tail -1
ls "$P/data/g6sp_train" | wc -l | sed 's/^/files: /'; du -sh "$P/data/g6sp_train" | cut -f1 | sed 's/^/size: /'
python3 - <<'PY'
import os
p = os.path.expanduser('~/work/plan/queue.txt')
pos = int(open(os.path.expanduser('~/work/plan/queue.pos')).read())
lines = open(p).read().splitlines()
done, waiting = lines[:pos + 1], lines[pos + 1:]
by = {l.split()[0]: l for l in waiting}
new = {'lab1': 'lab1 $PY scripts/plan_ceiling.py --episodes $P/data/g6sp_train --worlds 16 --ties --from-trick 7 --to-trick 12 --workers 8 --out $R.json'}
order = [n for n in ['@source', 'ceilTies', 'lab1', 'ceilT12', 'ceil64b', 'matrix1', 'fam1', 'matrix2'] if n in by or n in new]
out = [new.get(n) or by[n] for n in order]
tmp = p + '.new'
open(tmp, 'w').write('\n'.join(done + out) + '\n')
os.replace(tmp, p)
print('running:', done[-1].split()[0], '| waiting now:', ' '.join(l.split()[0] for l in out))
PY
df -h "$P" | tail -1 | awk '{print "disk free:", $4}'
