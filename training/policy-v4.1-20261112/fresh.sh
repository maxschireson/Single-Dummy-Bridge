#!/bin/bash
# fresh.sh NAME SEEN_DIR... : fetch the episodes that are in none of the SEEN directories into eps<NAME>, build them,
# and keep the deals the training set does not have as held-out set fresh<NAME>.npz (chain.sh's step, on its own).
set -uo pipefail
P=$HOME/work/p41; S=$HOME/work/p41src; T=$S/training/policy-v4.1-20261112; PY=$HOME/work/venv/bin/python
SCORER=$HOME/work/repo/models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz
FEEDS=('arena-gen6-*' 'arena-gen7-phase1-*' 'transfer/pre7-test-azure*-20261112')
name=$1; shift; seen=(); for d in "$@"; do seen+=(--seen "$d"); done
cd $S
$PY $T/fetch_feeds.py --out $P/eps$name --work $P/git --manifest $P/data/fetch$name.json "${seen[@]}" --jobs 8 "${FEEDS[@]}" > $P/logs/fetch$name.log 2>&1 || exit 1
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 $PY scripts/gen7_build_dataset.py --episodes $P/eps$name --scorer $SCORER --out $P/data/fresh${name}_raw.npz --workers ${WORKERS:-4} > $P/logs/build$name.log 2>&1 || exit 1
$PY $T/fresh_set.py $P/data/fresh${name}_raw.npz $P/data/fresh$name.npz $P/data/gen7_v41_train.npz > $P/logs/fresh$name.log 2>&1 || exit 1
echo "fresh$name done: $(cat $P/logs/fresh$name.log) $(date -u +%T)" >> $P/logs/timeline.log
