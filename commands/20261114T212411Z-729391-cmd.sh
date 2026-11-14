# boxctl: timeout=600
# loop session: read-only. Rollout net v2's epochs 2-4 (from its transfer branch) on the width runs' held-out rows (freshB), so
# every width run's epoch has v2's same epoch beside it. Two threads at Nice 15 beside the width run.
set -uo pipefail
W=$HOME/work/loop; S2=$W/src-lc; PY=$W/venv/bin/python; D=$HOME/work/plan/rnet2w/data
cd "$S2"; export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
git fetch -q --depth 1 origin transfer/rollout-net-v2-20261113 2>&1 | tail -1
for e in 2 3 4; do git show FETCH_HEAD:runs/w768/policy_epoch$e.npz > /tmp/v2_e$e.npz; done
nice -n 15 "$PY" scripts/score_rollout_nets.py --data "$D/freshB.npz" --net v2e2=/tmp/v2_e2.npz --net v2e3=/tmp/v2_e3.npz --net v2e4=/tmp/v2_e4.npz 2>&1 | grep -v Warning | grep "^v2" | cut -c1-160
