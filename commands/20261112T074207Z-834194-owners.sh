# boxctl: timeout=100
#!/bin/bash
W=$HOME/work; G=$W/g8p41; P=$W/p41; PY=$W/venv/bin/python; M=$G/models/cardplay
cd $G && git fetch -q --depth=1 origin feature/gen8-p41-20261112 && git show FETCH_HEAD:scripts/gen8_reading_bench.py > scripts/gen8_reading_bench.py
cat > $P/owners.sh <<'EOS'
#!/bin/bash
W=$HOME/work; G=$W/g8p41; P=$W/p41; PY=$W/venv/bin/python; M=$G/models/cardplay
cd $G
export BRIDGE_DDS_CACHE= OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
$PY scripts/gen8_reading_bench.py owners --episodes $P/epsB --out $P/runs/reading \
  --net v0=$M/gen7-policy-v0-2026-11-11/gen7_policy_v0.npz --net v2=$M/gen7-policy-v2-2026-11-11/gen7_policy_v2.npz \
  --net v4=$M/gen7-policy-v4-2026-11-11/gen7_policy_v4.npz --net v4.1=$M/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz \
  --net e5=$P/runs/w512e5/policy_epoch5_T.npz > $P/logs/owners.out 2>&1
echo "owners exit $? $(date -u +%T)" >> $P/logs/timeline.log
EOS
sudo systemd-run --unit=g8-owners --uid="$(id -un)" --working-directory="$G" --setenv=HOME="$HOME" -- /bin/bash $P/owners.sh 2>&1 | tail -1
date -u +%T; tail -2 $P/logs/timeline.log; cat $P/logs/eval_direct.log | cut -c1-330; cat $P/runs/reading/pools-0?.log | grep -c table
