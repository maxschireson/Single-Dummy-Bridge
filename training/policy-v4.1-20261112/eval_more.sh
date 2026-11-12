#!/bin/bash
# eval_more.sh TAG RUN : when the five-epoch run RUN (w512e5 or w768e5) has ended: fit its temperatures on B, fetch one more
# batch of fresh boards (TAG), and score it against v4 and the three-epoch net on every fresh set but B, with the same on B.
set -uo pipefail
TAG=$1; RUN=$2
P=$HOME/work/p41; S=$HOME/work/p41src; T=$S/training/policy-v4.1-20261112; PY=$HOME/work/venv/bin/python; M=$HOME/work/repo/models/cardplay
V4=$M/gen7-policy-v4-2026-11-11/gen7_policy_v4.npz
log() { echo "$1 $(date -u +%T)" >> $P/logs/timeline.log; }
while ! grep -q "$RUN exit" $P/logs/timeline.log; do sleep 5; done
grep -q "$RUN exit 0" $P/logs/timeline.log || exit 1
R=$P/runs/$RUN; L=$P/logs/eval_$RUN.log
export OPENBLAS_NUM_THREADS=3 OMP_NUM_THREADS=3
cd $S
{
echo "== temperatures fitted on B"
for e in 1 2 3 4 5; do $PY scripts/gen7_fit_temperature.py $R/policy_epoch$e.npz $P/data/freshB.npz 1 $R/policy_epoch${e}_T.npz; done
seen=($P/eps); for n in B C D E F G; do [ -d $P/eps$n ] && seen+=($P/eps$n); done
WORKERS=4 bash $T/fresh.sh $TAG "${seen[@]}" || echo "fresh $TAG failed"
parts=(); for n in C D E F G; do [ -e $P/data/fresh$n.npz ] && parts+=($P/data/fresh$n.npz); done
A=$P/data/freshALL_$TAG.npz
echo "== every fresh set but B together: $($PY $T/merge_sets.py $A "${parts[@]}")"
W512=$P/runs/w512/policy_epoch3_T.npz; W768=$P/runs/w768/policy_epoch3_T.npz
base=$([ $RUN = w512e5 ] && echo "w512=$W512" || echo "w768=$W768")
echo "== v4, three epochs, five epochs"
$PY scripts/gen7_compare_nets.py $A 1 0 v4=$V4 $base $RUN=$R/policy_epoch5_T.npz
echo "== its epochs 3, 4 and 5"
$PY scripts/gen7_compare_nets.py $A 1 0 $base e3=$R/policy_epoch3_T.npz e4=$R/policy_epoch4_T.npz e5=$R/policy_epoch5_T.npz | head -6
if [ $RUN = w768e5 ] && [ -e $P/runs/w512e5/policy_epoch5_T.npz ]; then
  echo "== five epochs: 512 wide against 768 wide"
  $PY scripts/gen7_compare_nets.py $A 1 0 w512=$W512 w512e5=$P/runs/w512e5/policy_epoch5_T.npz w768e5=$R/policy_epoch5_T.npz | head -5
fi
echo "== the same on B (the temperature set)"
$PY scripts/gen7_compare_nets.py $P/data/freshB.npz 1 0 v4=$V4 $base $RUN=$R/policy_epoch5_T.npz | head -5
echo "== trainer figures by deciding bot (0 = 6-32, 2 = 7s-32)"
for b in 0 2; do $PY scripts/gen7_score_nets.py $A --bot $b $base $RUN=$R/policy_epoch5_T.npz; done
echo "== heads"
$PY scripts/gen7_head_eval.py $A 1 0 $base $RUN=$R/policy_epoch5_T.npz
echo "== done $(date -u +%T)"
} > $L 2>&1
log "eval $RUN done"
bash $T/push_all.sh > $P/logs/push_$RUN.log 2>&1; log "push $RUN done"
