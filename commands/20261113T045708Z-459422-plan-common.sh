# boxctl: timeout=3600
# boxctl: timeout=3600
# plan session: one held-out set for both v2 nets, v1 and v4.1: boards that reached the feeds after azure2's last
# fetch (02:27), minus families in either v2 training set (azure2's train.npz and freshB; azure5's set is a subset of
# the boards before 02:19), scored with scripts/score_rollout_nets.py (numpy).
set -uo pipefail
P=$HOME/work/plan; S=$P/src; C=$P/common; PY=$HOME/work/venv/bin/python
mkdir -p $C/data $P/nets/v2w
export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
git -C $S fetch -q origin research/plan-leverage-g8-20261112 2>&1 | tail -1
G=$(git -C $S rev-parse FETCH_HEAD)
git -C $S show $G:scripts/score_rollout_nets.py | sed "s#^ROOT = .*#ROOT = Path('$S')#" > /tmp/score_rollout_nets.py
T=/tmp/rnet2tools; rm -rf $T; mkdir -p $T
for f in fetch_feeds.py fresh_set.py; do git -C $S show $G:training/rollout-net-v2-20261113/$f > $T/$f; done
git -C $S fetch -q --depth=1 origin transfer/rollout-net-v2w-20261113 2>&1 | tail -1
for e in 1 2 3; do git -C $S show FETCH_HEAD:runs/warm/policy_epoch$e.npz > $P/nets/v2w/policy_epoch$e.npz; done
ls -la $P/nets/v2w | tail -3
FEEDS=('arena-gen6-*' 'arena-gen7-*' 'arena-gen71-*' 'arena-gen8-*' 'arena-gen5rz*' 'transfer/pre7-test-azure*-20261112')
$PY $T/fetch_feeds.py --out $C/eps --work $C/git --manifest $C/data/fetch.json --seen $P/rnet1/eps --seen $P/rnet2/eps --seen $P/rnet2/epsB \
  --seen $P/rnet2/eps --jobs 8 "${FEEDS[@]}" 2>&1 | tail -2
cd $S
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 nice -n 5 $PY scripts/gen7_build_dataset.py --episodes $C/eps --scorer $P/../sdb-gen7/models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz \
  --policy-only --out $C/data/raw.npz --workers 6 2>&1 | tail -1
$PY $T/fresh_set.py $C/data/raw.npz $C/data/common.npz $P/rnet2/data/train.npz $P/rnet2/data/freshB.npz
nets="--net v41=$S/models/cardplay/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz --net v1ft=$P/rnet1/ft/policy.npz --net v1scr=$P/rnet1/scratch/policy.npz"
for e in 1 2 3 4 5; do nets="$nets --net s$e=$P/rnet2/w768/policy_epoch$e.npz"; done
for e in 1 2 3; do nets="$nets --net w$e=$P/nets/v2w/policy_epoch$e.npz"; done
OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 nice -n 5 $PY /tmp/score_rollout_nets.py --data $C/data/common.npz $nets --out $P/runs/common_scores.json 2>&1 | tail -13
$PY - <<'PY'
import json, os
d = json.load(open(os.path.expanduser('~/work/plan/runs/common_scores.json')))
for name, r in d.items():
    b = r['scores']['by_bot']
    print(name, ' '.join(f"{k}:{v['n']}:{v['nll']:.3f}/{v['agree']:.3f}/{v['regret'] if v['regret'] is not None else '-'}" for k, v in b.items()))
PY
