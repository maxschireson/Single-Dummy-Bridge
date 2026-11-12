# boxctl: timeout=300
# boxctl: timeout=120
# plan session: cheaper stand-ins for the bot in the reading bench, next on azure5.
set -uo pipefail
P=$HOME/work/plan
python3 - <<'PY'
import os
p = os.path.expanduser('~/work/plan/queue.txt')
pos = int(open(os.path.expanduser('~/work/plan/queue.pos')).read())
lines = open(p).read().splitlines()
done, waiting = lines[:pos + 1], lines[pos + 1:]
M = 'models/cardplay/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz'
new = ['@source 2f002765c0f5b67de70143536903378cf6c8daf3',
       f'rbs4 $PY scripts/plan_reading_bound.py --episodes $P/data/fresh_g6sp --net {M} --trick 6 --seeds 2 --files 120 --swaps --inner-samples 8 --inner-list 32 --workers 8 --out $R.json',
       f'rbs5 $PY scripts/plan_reading_bound.py --episodes $P/data/fresh_g6sp --net {M} --trick 6 --seeds 2 --files 120 --swaps --inner-samples 4 --inner-list 16 --workers 8 --out $R.json']
tmp = p + '.new'
open(tmp, 'w').write('\n'.join(done + new + waiting) + '\n')
os.replace(tmp, p)
print('running:', done[-1].split()[0], '| waiting now:', ' '.join(l.split()[0] for l in new + waiting))
PY
echo "position $(cat "$P/queue.pos"); $(tail -1 "$P/queue.log" | cut -c1-80)"
