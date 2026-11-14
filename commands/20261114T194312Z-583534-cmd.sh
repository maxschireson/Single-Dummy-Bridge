# boxctl: timeout=600
# loop session: read-only. Rollout net v2's epoch-1 net (from its transfer branch) and the 1,536-wide net's epoch 1, on the
# same held-out rows (freshB), so the two first epochs are compared on one set. Two threads at Nice 10 beside the collection.
set -uo pipefail
W=$HOME/work/loop; S2=$W/src-lc; PY=$W/venv/bin/python; D=$HOME/work/plan/rnet2w/data
cd "$S2"; export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
git fetch -q --depth 1 origin transfer/rollout-net-v2-20261113 2>&1 | tail -1
git show FETCH_HEAD:runs/w768/policy_epoch1.npz > /tmp/v2_e1.npz && ls -la /tmp/v2_e1.npz | cut -c1-100
nice -n 10 "$PY" scripts/score_rollout_nets.py --data "$D/freshB.npz" --net v2e1=/tmp/v2_e1.npz --net w1536e1="$W/exp-width/w1536-8core/policy_epoch1.npz" \
  --net v2e5=models/cardplay/rollout-net-v2-20261113/policy_epoch5.npz 2>&1 | grep -v Warning | tail -5 | cut -c1-200
date -u +%T
