# boxctl: timeout=240
# boxctl: timeout=240
# plan session: azure5: rollout net v2 warm start (Max, 01:26): pause my own match6 (it resumes from its results, on
# its own source 0d1db2b) and run training/rollout-net-v2-20261113/chain.sh at 40adc36 from the 768-wide 5-epoch net of
# the v4.1 runs (transfer/gen7-policy-v4.1-box-20261112 runs/w768e5/policy_epoch5.npz), lr 5e-4, 3 epochs; then seat1,
# match6 again, match5, rbc2a, rbc2b.
set -uo pipefail
P=$HOME/work/plan
mkdir -p $P/nets
export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
git -C $P/src fetch -q --depth=1 --filter=blob:none origin transfer/gen7-policy-v4.1-box-20261112 2>&1 | tail -2
git -C $P/src show FETCH_HEAD:runs/w768e5/policy_epoch5.npz > $P/nets/w768e5_epoch5.npz
python3 -c "import numpy as np; z=np.load('$P/nets/w768e5_epoch5.npz'); print('init net', z['wt0'].shape, int(z['kind']), len(z.files), 'arrays')"
S=$(find $HOME/work -name hand_fit_v0.npz -path "*hand-fit-scorer-v0-2026-11-11*" 2>/dev/null | head -1); ln -sf "$S" $P/nets/hand_fit_v0.npz; ls -la $P/nets/hand_fit_v0.npz
df -h $HOME | tail -1; free -g | sed -n 2p
python3 - <<'PY'
import os
p = os.path.expanduser('~/work/plan/queue.txt')
pos = int(open(os.path.expanduser('~/work/plan/queue.pos')).read())
lines = open(p).read().splitlines()
done, waiting = lines[:pos + 1], lines[pos + 1:]
assert done[-1].split()[0] == 'match6', done[-1][:60]
assert not any(l.split()[:1] == ['rnet2w'] for l in lines), 'rnet2w already queued'
seat = [l for l in waiting if l.split()[:1] == ['seat1']]
rest = [l for l in waiting if l.split()[:1] != ['seat1']]
job = ('rnet2w W=$P/rnet2w RUN=warm INIT=$P/nets/w768e5_epoch5.npz LR=5e-4 EPOCHS=3 SCORER=$P/nets/hand_fit_v0.npz '
       'BRANCH=transfer/rollout-net-v2w-20261113 CMP_NETS="$P/nets/rnet1/ft.npz $P/nets/rnet1/scratch.npz" '
       'bash training/rollout-net-v2-20261113/chain.sh')
out = ['@source 40adc36c98cb68b8d6b3724d1289b63f36efd413', job] + seat + ['@source 0d1db2bb9944abc83f0bc6de64d2e47299c2bf44', done[-1]] + rest
tmp = p + '.new'
open(tmp, 'w').write('\n'.join(done + out) + '\n')
os.replace(tmp, p)
print('waiting now:', ' | '.join(l.split()[0] for l in out))
PY
pkill -f "pair prr-32-v41~7s-32-v41" || echo "nothing to stop"
sleep 60
echo "position $(cat "$P/queue.pos")"; tail -3 "$P/queue.log" | cut -c1-150; wc -l < "$P/runs/match6/results.jsonl"; tail -4 "$P/rnet2w/logs/timeline.log" 2>/dev/null | cut -c1-300
