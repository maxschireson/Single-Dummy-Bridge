# boxctl: timeout=180
# boxctl: timeout=180
# plan session: azure5: grade rollout net v2 (scratch epoch 5, warm epoch 3) as playout seats on the report's 512-layout
# bench, told the table's bots are Gen 6 (@6-32:6-32) and once with the ids unknown; queued after match6, before match5.
set -uo pipefail
P=$HOME/work/plan
mkdir -p $P/nets/v2
export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
git -C $P/src fetch -q --depth=1 origin transfer/rollout-net-v2-20261113 2>&1 | tail -1
git -C $P/src show FETCH_HEAD:runs/w768/policy_epoch5.npz > $P/nets/v2/policy_epoch5.npz
cp -f $P/rnet2w/warm/policy_epoch3.npz $P/nets/v2w/policy_epoch3.npz 2>/dev/null || { mkdir -p $P/nets/v2w; cp -f $P/rnet2w/warm/policy_epoch3.npz $P/nets/v2w/; }
ls -la $P/nets/v2 $P/nets/v2w | grep npz
python3 - <<'PY'
import os
p = os.path.expanduser('~/work/plan/queue.txt')
pos = int(open(os.path.expanduser('~/work/plan/queue.pos')).read())
lines = open(p).read().splitlines()
done, waiting = lines[:pos + 1], lines[pos + 1:]
assert done[-1].split()[0] == 'match6', done[-1][:60]
assert not any(l.split()[:1] == ['seat2'] for l in lines), 'already queued'
V2 = '$P/nets/v2/policy_epoch5.npz'; V2W = '$P/nets/v2w/policy_epoch3.npz'
nets = f'v2s={V2}@6-32:6-32,v2w={V2W}@6-32:6-32,v2wu={V2W}'
job = ('seat2 $PY scripts/plan_bench.py --episodes $P/data/fresh_g6sp --nets "$NETS,' + nets + '" '
       '--sims "v2s:top;v2w:top;v2w:blend;v2wu:top" --from-trick 3 --to-trick 6 --files 1000 --seed 1 --layouts 512 --max-gap 0.25 --workers 8 --out $R.json')
out = ['@source 9e6c3d940b26e9d684f37bbd0cb28efbf72af89c', job, '@source 0d1db2bb9944abc83f0bc6de64d2e47299c2bf44'] + waiting
tmp = p + '.new'
open(tmp, 'w').write('\n'.join(done + out) + '\n')
os.replace(tmp, p)
print('waiting now:', ' | '.join(l[:60] for l in out))
PY
wc -l < $P/runs/match6/results.jsonl
