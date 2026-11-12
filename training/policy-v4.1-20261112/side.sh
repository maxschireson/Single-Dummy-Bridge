#!/bin/bash
# Side jobs while the first net trains: the old nets on held-out set B, and the fork pairs of the training set and of B.
set -uo pipefail
P=$HOME/work/p41; S=$HOME/work/p41src; PY=$HOME/work/venv/bin/python; M=$HOME/work/repo/models/cardplay
V4=$M/gen7-policy-v4-2026-11-11/gen7_policy_v4.npz; V31=$M/gen7-policy-v3.1-2026-11-11/gen7_policy_v3.1.npz
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
log() { echo "$1 $(date -u +%T)" >> $P/logs/timeline.log; }
cd $S
while ! grep -q "freshB done" $P/logs/timeline.log; do sleep 5; done
{ $PY scripts/gen7_score_nets.py $P/data/freshB.npz v3.1=$V31 v4=$V4; for b in 0 2; do $PY scripts/gen7_score_nets.py $P/data/freshB.npz --bot $b v4=$V4; done; } > $P/logs/scoreB_old.log 2>&1
log "scoreB_old done"
$PY scripts/gen7_pairs.py --episodes $P/eps --set $P/data/gen7_v41_train.npz --out $P/data/pairsA.npz --workers 3 > $P/logs/pairsA.log 2>&1; log "pairsA exit $?"
$PY scripts/gen7_pairs.py --episodes $P/epsB --set $P/data/freshB_raw.npz --out $P/data/pairsB.npz --workers 2 > $P/logs/pairsB.log 2>&1; log "pairsB exit $?"
