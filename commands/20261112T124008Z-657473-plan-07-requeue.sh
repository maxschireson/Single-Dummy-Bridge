# boxctl: timeout=300
# boxctl: timeout=120
# plan session: reorder and extend the waiting part of ~/work/plan/queue.txt (lines already started are untouched).
set -uo pipefail
P=$HOME/work/plan
python3 - <<'PY'
import os
p = os.path.expanduser('~/work/plan/queue.txt')
pos = int(open(os.path.expanduser('~/work/plan/queue.pos')).read())
lines = open(p).read().splitlines()
done, waiting = lines[:pos + 1], lines[pos + 1:]          # line pos+1 (1-based) is running now
by = {l.split()[0]: l for l in waiting}
M = 'models/cardplay/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz'
new = {
 'ceil64': 'ceil64 $PY scripts/plan_ceiling.py --episodes $P/data/fresh_g6sp --worlds 64 --max-gap 0.25 --skip-files 500 --files 500 --workers 8 --out $R.json',
 'ceil16c': 'ceil16c $PY scripts/plan_ceiling.py --episodes $P/data/fresh_g6sp --worlds 16 --skip-files 1000 --workers 8 --out $R.json',
}
order = ['@source', 'ceil64', 'rb1', 'ceilT12', 'bel2a', 'matrix1', 'ceil16c', 'fam1', 'matrix2']
out = []
for name in order:
    if name == '@source':
        out.append('@source ed3c31130ed06c5b4312f2ea9eb1c7c0d623044e')
    elif name in new:
        out.append(new[name])
    elif name in by:
        out.append(by[name])
    else:
        raise SystemExit(f'{name} is not waiting: nothing changed')
tmp = p + '.new'
open(tmp, 'w').write('\n'.join(done + out) + '\n')
os.replace(tmp, p)
print('running:', done[-1].split()[0], '| waiting now:', ' '.join(l.split()[0] if not l.startswith('@') else '@source' for l in out))
PY
echo "position $(cat "$P/queue.pos"); $(tail -1 "$P/queue.log" | cut -c1-80)"; tail -1 "$P/runs/ceilT712.log" | cut -c1-80
