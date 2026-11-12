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
new = {
 'wide1': 'wide1 $PY scripts/plan_bench.py --episodes $P/data/fresh_g6sp --nets $NETS --sims "v41:top;v4:top;v0:top;v41:blend" --from-trick 3 --to-trick 6 --files 1000 --seed 1 --layouts 512 --max-gap 0.25 --workers 8 --out $R.json',
 'wide2': 'wide2 $PY scripts/plan_bench.py --episodes $P/data/fresh_g6sp --nets $NETS --sims "v41:hyb3" --from-trick 3 --to-trick 6 --files 1000 --seed 1 --layouts 128 --max-gap 0.25 --workers 8 --out $R.json',
}
order = ['@source', 'wide1', 'wide2', 'rb1', 'ceilT12', 'matrix1', 'ceil16c', 'fam1', 'matrix2']
out = []
for name in order:
    if name == '@source':
        out.append('@source 7a24cf781834417640e144c1b3f9fd7710c1340d')
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
echo "position $(cat "$P/queue.pos"); $(tail -1 "$P/queue.log" | cut -c1-80)"; tail -1 "$P/runs/ceil64.log" | cut -c1-80; cat "$P/nets.txt" | cut -c1-300
