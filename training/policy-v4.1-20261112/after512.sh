#!/bin/bash
# When the 512-wide run ends: score it, push; then the fork pairs of set C and the result head on the 512-wide net, and push again.
set -uo pipefail
P=$HOME/work/p41; S=$HOME/work/p41src; T=$S/training/policy-v4.1-20261112; PY=$HOME/work/venv/bin/python
log() { echo "$1 $(date -u +%T)" >> $P/logs/timeline.log; }
while ! grep -q "w512 done\|w512 FAILED\|CHAIN STOPPED" $P/logs/timeline.log; do sleep 5; done
grep -q "w512 done" $P/logs/timeline.log || exit 1
bash $T/evalnet.sh 512
bash $T/push_results.sh > $P/logs/push1.log 2>&1; log "push1 done"
while ! grep -q "pairsB exit" $P/logs/timeline.log; do sleep 5; done
cd $S
OPENBLAS_NUM_THREADS=1 $PY scripts/gen7_pairs.py --episodes $P/epsC --set $P/data/freshC_raw.npz --out $P/data/pairsC.npz --workers 2 > $P/logs/pairsC.log 2>&1; log "pairsC exit $?"
OPENBLAS_NUM_THREADS=3 OMP_NUM_THREADS=3 $PY scripts/gen7_result_head.py --net $P/runs/w512/policy_epoch3_T.npz --set $P/data/gen7_v41_train.npz --pairs $P/data/pairsA.npz \
  --test $P/data/freshB_raw.npz $P/data/pairsB.npz --test $P/data/freshC_raw.npz $P/data/pairsC.npz --out $P/runs/result_head > $P/logs/result_head.log 2>&1; log "result_head exit $?"
bash $T/push_results.sh > $P/logs/push2.log 2>&1; log "push2 done"
