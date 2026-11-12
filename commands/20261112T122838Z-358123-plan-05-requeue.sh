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
 'ceilT712': 'ceilT712 $PY scripts/plan_ceiling.py --episodes $P/data/fresh_g6sp --worlds 16 --from-trick 7 --to-trick 12 --files 500 --workers 8 --out $R.json',
 'ceilT12': 'ceilT12 $PY scripts/plan_ceiling.py --episodes $P/data/fresh_g6sp --worlds 16 --from-trick 1 --to-trick 2 --files 300 --workers 8 --out $R.json',
 'rb1': f'rb1 $PY scripts/plan_reading_bound.py --episodes $P/data/fresh_g6sp --net {M} --trick 6 --candidates 40 --seeds 2 --files 40 --workers 8 --out $R.json',
 'bel2a': 'bel2a $PY scripts/plan_bench.py --episodes $P/data/fresh_g6sp --nets $NETS --sims "v41:top;v41:hyb3;v4:hyb3;v0:hyb3" --from-trick 3 --to-trick 6 --files 800 --seed 1 --workers 8 --out $R.json',
}
order = ['ceilT712', 'ceil16b', 'ceilT12', '@source', 'rb1', 'bel2a', 'matrix1', 'fam1', 'matrix2']
out = []
for name in order:
    if name == '@source':
        out.append('@source 742b5930d57c2c9f3664f2bbea7d1234268b36d1')
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
echo "position $(cat "$P/queue.pos"); $(tail -1 "$P/queue.log" | cut -c1-80)"; tail -1 "$P/runs/ceil16a.log" | cut -c1-80; grep -n "source" "$P/queue.sh" | head -5
