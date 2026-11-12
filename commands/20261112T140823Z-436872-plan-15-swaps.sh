# boxctl: timeout=300
# boxctl: timeout=120
# plan session: put the single-card reading bench ahead of the waiting jobs on azure5.
set -uo pipefail
P=$HOME/work/plan
python3 - <<'PY'
import os
p = os.path.expanduser('~/work/plan/queue.txt')
pos = int(open(os.path.expanduser('~/work/plan/queue.pos')).read())
lines = open(p).read().splitlines()
done, waiting = lines[:pos + 1], lines[pos + 1:]
M = 'models/cardplay/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz'
new = ['@source b0230a0516fbc35bc6204577e670eeacc73434e8',
       f'rbs1 $PY scripts/plan_reading_bound.py --episodes $P/data/fresh_g6sp --net {M} --trick 6 --seeds 2 --files 120 --swaps --workers 8 --out $R.json',
       f'rbs2 $PY scripts/plan_reading_bound.py --episodes $P/data/fresh_g6sp --net {M} --trick 4 --seeds 2 --files 80 --skip-files 120 --swaps --workers 8 --out $R.json',
       f'rbs3 $PY scripts/plan_reading_bound.py --episodes $P/data/fresh_g6sp --net {M} --trick 9 --seeds 2 --files 80 --skip-files 200 --swaps --workers 8 --out $R.json']
tmp = p + '.new'
open(tmp, 'w').write('\n'.join(done + new + waiting) + '\n')
os.replace(tmp, p)
print('running:', done[-1].split()[0], '| waiting now:', ' '.join(l.split()[0] for l in new + waiting))
PY
echo "position $(cat "$P/queue.pos"); $(tail -1 "$P/queue.log" | cut -c1-80)"; tail -1 "$P/runs/ceilT712b.log" | cut -c1-80
