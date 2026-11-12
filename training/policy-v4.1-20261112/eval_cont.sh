#!/bin/bash
# eval_cont.sh RUN WIDTH : when a continuation run (more epochs from a finished net's weights) has ended, fit its temperature on B
# and score it against v4 and the net it started from, on sets C and D together and on B.
set -uo pipefail
RUN=$1; W=$2
P=$HOME/work/p41; S=$HOME/work/p41src; T=$S/training/policy-v4.1-20261112; PY=$HOME/work/venv/bin/python; M=$HOME/work/repo/models/cardplay
V4=$M/gen7-policy-v4-2026-11-11/gen7_policy_v4.npz
log() { echo "$1 $(date -u +%T)" >> $P/logs/timeline.log; }
while ! grep -q "$RUN exit" $P/logs/timeline.log; do sleep 5; done
grep -q "$RUN exit 0" $P/logs/timeline.log || exit 1
R=$P/runs/$RUN; BASE=$P/runs/w$W/policy_epoch3_T.npz
export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2
cd $S
{
echo "== temperatures fitted on B"
nets=""
for f in $R/policy_epoch?.npz; do e=$(basename $f .npz); e=${e#policy_epoch}; $PY scripts/gen7_fit_temperature.py $f $P/data/freshB.npz 1 $R/policy_epoch${e}_T.npz; nets="$nets plus$e=$R/policy_epoch${e}_T.npz"; done
for set in CD B; do
  echo "== v4, the three-epoch net, and the continuation, on fresh $set"
  $PY scripts/gen7_compare_nets.py $P/data/fresh$set.npz 1 0 v4=$V4 three=$BASE $nets
done
echo "== heads on fresh CD"
$PY scripts/gen7_head_eval.py $P/data/freshCD.npz 1 0 three=$BASE $nets
echo "== done $(date -u +%T)"
} > $P/logs/eval_$RUN.log 2>&1
log "eval $RUN done"
