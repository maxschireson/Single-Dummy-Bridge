# boxctl: timeout=180
# boxctl: timeout=180
# plan session: azure5: grade rollout net v1 as a playout seat (the report's 512-layout bench, as `wide1`, with v1's
# two nets and v4.1 on the same pairs; about 16 minutes), queued right after match6 and before match5.
set -uo pipefail
P=$HOME/work/plan
mkdir -p $P/nets/rnet1
export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
git -C $P/src fetch -q --depth=1 origin transfer/rollout-net-v1-20261113 2>&1 | tail -2
for n in ft scratch; do git -C $P/src show FETCH_HEAD:runs/$n/policy.npz > $P/nets/rnet1/$n.npz; done
ls -la $P/nets/rnet1
python3 - <<'PY'
import os
p = os.path.expanduser('~/work/plan/queue.txt')
pos = int(open(os.path.expanduser('~/work/plan/queue.pos')).read())
lines = open(p).read().splitlines()
done, waiting = lines[:pos + 1], lines[pos + 1:]
assert done[-1].split()[0] == 'match6', done[-1][:60]
assert not any(l.split()[:1] == ['seat1'] for l in lines), 'seat1 already queued'
job = ('seat1 $PY scripts/plan_bench.py --episodes $P/data/fresh_g6sp --nets "$NETS,ft=$P/nets/rnet1/ft.npz,scr=$P/nets/rnet1/scratch.npz" '
       '--sims "v41:top;ft:top;scr:top;ft:blend" --from-trick 3 --to-trick 6 --files 1000 --seed 1 --layouts 512 --max-gap 0.25 --workers 8 --out $R.json')
tmp = p + '.new'
open(tmp, 'w').write('\n'.join(done + [job] + waiting) + '\n')
os.replace(tmp, p)
print('waiting now:', ' | '.join(l.split()[0] for l in [job] + waiting))
PY
git -C $P/src remote get-url origin | sed 's#//.*@#//#'
