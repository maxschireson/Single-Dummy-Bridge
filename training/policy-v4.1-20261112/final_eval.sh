#!/bin/bash
# Last step on the box, when the 768-wide run ends: one more batch of fresh boards (D); every net on C and D together;
# the result head again with the pairs of B, C and D as its test. Then push.
set -uo pipefail
P=$HOME/work/p41; S=$HOME/work/p41src; T=$S/training/policy-v4.1-20261112; PY=$HOME/work/venv/bin/python; M=$HOME/work/repo/models/cardplay
V4=$M/gen7-policy-v4-2026-11-11/gen7_policy_v4.npz; V31=$M/gen7-policy-v3.1-2026-11-11/gen7_policy_v3.1.npz
log() { echo "$1 $(date -u +%T)" >> $P/logs/timeline.log; }
if [ "${1:-wait}" = wait ]; then
  while ! grep -q "w768 done\|w768 exit\|w768 FAILED" $P/logs/timeline.log; do sleep 5; done
fi
while ! grep -q "freshC done" $P/logs/timeline.log; do sleep 5; done
WORKERS=6 bash $T/fresh.sh D $P/eps $P/epsB $P/epsC || log "fresh D failed"
cd $S
export OPENBLAS_NUM_THREADS=4 OMP_NUM_THREADS=4
DEALS=$($PY -c "import json; print(json.loads(open('$P/logs/buildA.log').read().strip().splitlines()[-1])['deals'])")
if [ -e $P/data/freshD.npz ]; then $PY $T/merge_sets.py $P/data/freshCD.npz $P/data/freshC.npz $P/data/freshD.npz > $P/logs/mergeCD.log 2>&1; else cp $P/data/freshC.npz $P/data/freshCD.npz; fi
NEW="w512=$P/runs/w512/policy_epoch3_T.npz"; [ -e $P/runs/w768/policy_epoch3_T.npz ] && NEW="$NEW w768=$P/runs/w768/policy_epoch3_T.npz"
{
echo "== every net on fresh C and D together: $(cat $P/logs/mergeCD.log 2>/dev/null)"
TRAIN_DEALS=v3.1:12111,v4:17207,w512:$DEALS $PY scripts/gen7_compare_nets.py $P/data/freshCD.npz 1 0 v3.1=$V31 v4=$V4 $NEW
echo "== trainer figures, all rows and by deciding bot (0 = 6-32, 2 = 7s-32)"
$PY scripts/gen7_score_nets.py $P/data/freshCD.npz v4=$V4 $NEW
for b in 0 2; do $PY scripts/gen7_score_nets.py $P/data/freshCD.npz --bot $b v4=$V4 $NEW; done
echo "== heads"
$PY scripts/gen7_head_eval.py $P/data/freshCD.npz 1 0 v4=$V4 $NEW
echo "== done $(date -u +%T)"
} > $P/logs/final_eval.log 2>&1
log "final_eval done"
bash $T/push_results.sh > $P/logs/push4.log 2>&1; log "push4 done"
if [ -e $P/data/freshD_raw.npz ]; then
  OPENBLAS_NUM_THREADS=1 $PY scripts/gen7_pairs.py --episodes $P/epsD --set $P/data/freshD_raw.npz --out $P/data/pairsD.npz --workers 4 > $P/logs/pairsD.log 2>&1; log "pairsD exit $?"
  while ! grep -q "result_head exit" $P/logs/timeline.log; do sleep 5; done
  OPENBLAS_NUM_THREADS=6 OMP_NUM_THREADS=6 $PY scripts/gen7_result_head.py --net $P/runs/w512/policy_epoch3_T.npz --set $P/data/gen7_v41_train.npz --pairs $P/data/pairsA.npz \
    --test $P/data/freshB_raw.npz $P/data/pairsB.npz --test $P/data/freshC_raw.npz $P/data/pairsC.npz --test $P/data/freshD_raw.npz $P/data/pairsD.npz \
    --out $P/runs/result_head_final > $P/logs/result_head_final.log 2>&1; log "result_head_final exit $?"
  bash $T/push_results.sh > $P/logs/push5.log 2>&1; log "push5 done"
fi
log "final end"
