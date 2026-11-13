# boxctl: timeout=1800
# boxctl: timeout=1800
# loop session: the int8 benchmark (rollout net v2, round 2's net, policy v4.1) on azure5 with the collection paused for
# clean clocks, from the second checkout (the collection's source is untouched); the collection restarts after.
set -euo pipefail
W=$HOME/work/loop; S=$W/src; S2=$W/src-lc; T=$S/training/rollout-loop-20261113; PY=$W/venv/bin/python
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q 5472ef479ccaf322fda08a03c53cb42c843f4f74
sudo systemctl stop loop-collect loop-collect-b
cd "$S2"; export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
timeout 1200 "$PY" training/rollout-loop-20261113/bench/int8.py --rows "$W/r2/val.npz"   models/cardplay/rollout-net-v2-20261113/policy_epoch5.npz models/cardplay/stu-net-r2-20261113/policy.npz   models/cardplay/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz 2>&1 | grep -v Warning | tail -20 || echo "bench failed"
sudo systemctl reset-failed loop-collect loop-collect-b 2>/dev/null || true
sudo systemd-run --unit=loop-collect --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-azure5.txt"
sudo systemd-run --unit=loop-collect-b --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-azure5b.txt"
sleep 10; systemctl is-active loop-collect loop-collect-b | tr '\n' ' '; date -u +%FT%TZ
