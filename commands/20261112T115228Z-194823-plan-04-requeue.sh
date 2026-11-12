# boxctl: timeout=120
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
 'bel1c': 'bel1c $PY scripts/plan_bench.py --episodes $P/data/fresh_g6sp --nets $NETS --sims "v41:hyb5;v41:hyb8;v41:map3" --from-trick 3 --to-trick 6 --files 800 --workers 8 --out $R.json',
 'bel1b': 'bel1b $PY scripts/plan_bench.py --episodes $P/data/fresh_g6sp --nets $NETS --sims "v0:hyb3;v2:hyb3;v4:hyb3;v0:map;v4:map" --from-trick 3 --to-trick 6 --files 800 --workers 8 --out $R.json',
 'matrix2': f'matrix2 $PY scripts/plan_matrix_study.py --episodes $P/data/fresh_g6sp --net {M} --decisions 800 --own-layouts 4 --families patterns --workers 8 --out $R.json',
}
order = ['ceil16a', 'bel1c', 'matrix1', 'bel1b', 'ceil16b', 'fam1', '@source', 'matrix2']
out = []
for name in order:
    if name == '@source':
        out.append('@source 562271ce58a5234c99a848c104c4e0985eb24ec0')
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
echo "position $(cat "$P/queue.pos"); $(tail -1 "$P/queue.log" | cut -c1-80)"; tail -1 "$P/runs/bel1a.log" | cut -c1-80
