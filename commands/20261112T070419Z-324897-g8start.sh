# boxctl: timeout=400
#!/bin/bash
set -uo pipefail
W=$HOME/work; G=$W/g8p41; P=$W/p41; PY=$W/venv/bin/python; M=$G/models/cardplay
cd $G
rm -rf /tmp/rbtest
BRIDGE_DDS_CACHE= OPENBLAS_NUM_THREADS=1 nice -n 19 $PY scripts/gen8_reading_bench.py pools --episodes $P/epsE --skip-families $P/data/gen7_v41_train.npz --out /tmp/rbtest --tables 1 \
  --net v0=$M/gen7-policy-v0-2026-11-11/gen7_policy_v0.npz --net v2=$M/gen7-policy-v2-2026-11-11/gen7_policy_v2.npz --net v4=$M/gen7-policy-v4-2026-11-11/gen7_policy_v4.npz \
  --net v4.1=$M/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz --net e5=$P/runs/w512e5/policy_epoch5_T.npz 2>&1 | tail -5
cat /tmp/rbtest/pools-00.log
nice -n 19 $PY scripts/gen8_reading_bench.py report --out /tmp/rbtest 2>&1 | cut -c1-250 | head -12
sudo systemd-run --unit=g8-reading-start --uid="$(id -un)" --working-directory="$G" --setenv=HOME="$HOME" -- /bin/bash $P/reading_start.sh 2>&1 | tail -1
date -u +%T; tail -2 $P/logs/timeline.log; cut -c1-330 $P/logs/w768e5.out | tail -1; tail -c 60 $P/logs/w768e5.err
