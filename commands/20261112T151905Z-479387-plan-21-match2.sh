# boxctl: timeout=300
# boxctl: timeout=120
# plan session: on azure5, a played test of self-simulation from trick 5 after the layout walks.
set -uo pipefail
P=$HOME/work/plan
python3 - <<'PY'
import os
p = os.path.expanduser('~/work/plan/queue.txt')
pos = int(open(os.path.expanduser('~/work/plan/queue.pos')).read())
lines = open(p).read().splitlines()
done, waiting = lines[:pos + 1], lines[pos + 1:]
by = {l.split()[0]: l for l in waiting}
new = {'match2': 'match2 PYTHONPATH=$P/pylib $PY scripts/plan_match.py --source $P/capsule/recovery --bots configs/plan-bots.json --pair pr75x-32-v41~7s-32-v41 --deals 1600 --seed 131 --workers 8 --out $R'}
order = [n for n in ['rbs3', 'ceilT12', '@source', 'rbc2', 'match2', 'rbc1', 'wide3', 'ceil16c'] if n in by or n in new or n == '@source']
out = []
for name in order:
    if name == '@source':
        out.append('@source f80593e1a02d5587b6df3f534b21e301c133ca22')
    elif name in new:
        out.append(new[name])
    else:
        out.append(by[name])
tmp = p + '.new'
open(tmp, 'w').write('\n'.join(done + out) + '\n')
os.replace(tmp, p)
print('running:', done[-1].split()[0], '| waiting now:', ' '.join(l.split()[0] for l in out))
PY
echo "position $(cat "$P/queue.pos"); $(tail -1 "$P/queue.log" | cut -c1-80)"
cd "$P/src" && OPENBLAS_NUM_THREADS=1 BRIDGE_DDS_CACHE= PYTHONPATH=$P/pylib timeout 100 $HOME/work/venv/bin/python -c "
import sys; sys.path.insert(0,'scripts'); sys.path.insert(0,'.')
import h5py, json
from pathlib import Path
m=json.load(open('$P/capsule/recovery/manifest.json')); print('capsule manifest bots', len(m['bots']), 'roster', m['roster'][:4])
" 2>&1 | tail -2
