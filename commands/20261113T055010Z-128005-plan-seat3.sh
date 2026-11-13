# boxctl: timeout=180
# boxctl: timeout=180
# plan session: azure5: seat2 told the v2 nets nothing (rollouts read every bot as unknown; fixed in b54d6ca). Grade
# them again told the table is Gen 6 (seat3, about 10 minutes), then match5 resumes.
set -uo pipefail
P=$HOME/work/plan
python3 - <<'PY'
import os
p = os.path.expanduser('~/work/plan/queue.txt')
pos = int(open(os.path.expanduser('~/work/plan/queue.pos')).read())
lines = open(p).read().splitlines()
done, waiting = lines[:pos + 1], lines[pos + 1:]
cur = done[-1].split()[0]
assert cur in ('match5', 'seat2'), done[-1][:60]
assert not any(l.split()[:1] == ['seat3'] for l in lines), 'already queued'
V2 = '$P/nets/v2/policy_epoch5.npz'; V2W = '$P/nets/v2w/policy_epoch3.npz'
job = ('seat3 $PY scripts/plan_bench.py --episodes $P/data/fresh_g6sp --nets "$NETS,v2s=' + V2 + '@6-32:6-32,v2w=' + V2W + '@6-32:6-32" '
       '--sims "v2s:top;v2w:top" --from-trick 3 --to-trick 6 --files 1000 --seed 1 --layouts 512 --max-gap 0.25 --workers 8 --out $R.json')
if cur == 'match5':      # pause it again: it resumes from its results after seat3
    out = ['@source b54d6cadb9127712963bbced0802d9f165509127', job, '@source 0d1db2bb9944abc83f0bc6de64d2e47299c2bf44', done[-1]] + waiting
else:                    # seat2 still running: seat3 right after it, before the @source line for match5
    out = ['@source b54d6cadb9127712963bbced0802d9f165509127', job] + waiting
tmp = p + '.new'
open(tmp, 'w').write('\n'.join(done + out) + '\n')
os.replace(tmp, p)
print('current', cur, '; waiting now:', ' | '.join(l[:50] for l in out))
open('/tmp/plan_cur', 'w').write(cur)
PY
[ "$(cat /tmp/plan_cur)" = match5 ] && { pkill -f "pair cl-32-v41~7s-32-v41" || true; sleep 20; }
echo "position $(cat $P/queue.pos)"; tail -3 $P/queue.log | cut -c1-120
