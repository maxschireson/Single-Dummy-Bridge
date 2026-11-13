# boxctl: timeout=600
# boxctl: timeout=600
# plan session: early look: v4.1, v1 ft and this run's latest saved epoch on this run's own held-out boards (numpy).
set -uo pipefail
P=$HOME/work/plan; W=$P/rnet2; S=$P/src
export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
git -C $S fetch -q origin research/plan-leverage-g8-20261112 2>&1 | tail -1
git -C $S show FETCH_HEAD:scripts/score_rollout_nets.py | sed "s#^ROOT = .*#ROOT = Path('$S')#" > /tmp/score_rollout_nets.py
FT=$( [ -f $P/rnet1/ft/policy.npz ] && echo $P/rnet1/ft/policy.npz || echo $P/nets/rnet1/ft.npz )
E=$(ls $W/w768/policy_epoch*.npz | sort -V | tail -1); echo "latest: $E"
nets="--net v41=$S/models/cardplay/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz --net v1ft=$FT"
for f in $(ls $W/w768/policy_epoch*.npz | sort -V); do n=$(basename $f .npz); nets="$nets --net ${n#policy_}=$f"; done
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 nice -n 5 $HOME/work/venv/bin/python /tmp/score_rollout_nets.py --data $W/data/freshB.npz $nets --out $P/runs/early_rnet2.json 2>&1 | tail -8
$HOME/work/venv/bin/python - <<'PY'
import json, os
d = json.load(open(os.path.expanduser('~/work/plan/runs/early_rnet2.json')))
for name, r in d.items():
    b = r['scores']['by_bot']
    print(name, ' '.join(f"{k}:{v['nll']:.3f}/{v['regret'] if v['regret'] is not None else '-'}" for k, v in b.items() if k in ('8s-32', '8c-32', '71s-32', '7s-32', 'ben64', '6-32')))
PY
