#!/usr/bin/env bash
# E9-11 on a box (team/gen9 experiments/E9-11.md): 9r-32 (8p-32 plus the replay reader, house-gen6) against 8p-32,
# and both against 7s-32 on the same deals. Run from the repository root of feature/gen9-bidding-cards (or a merge).
#
#   SRC=~/capsule/recovery OUT=~/runs/e9-11 WORKERS=8 bash scripts/gen9_e9_11_job.sh
#
# Seed 9112 (the sandbox pilot used 9111). Pairs run in order of priority; each resumes from its results.jsonl.
set -euo pipefail
SRC=${SRC:-$HOME/capsule/recovery}
OUT=${OUT:-$HOME/runs/e9-11}
W=${WORKERS:-$(nproc)}
N=${N:-1600}
SEED=${SEED:-9112}
BOTS=configs/gen9-bidding-bots.json
mkdir -p "$OUT"
run() {               # pair
  echo "$(date -u +%FT%TZ) start $1 ($N boards, seed $SEED)" | tee -a "$OUT/job.log"
  BRIDGE_DDS_CACHE= python3 scripts/gen9_match.py --source "$SRC" --bots "$BOTS" --pair "$1" --deals "$N" --seed "$SEED" \
    --workers "$W" --out "$OUT/$1-$SEED" 2>&1 | tail -3 | tee -a "$OUT/job.log"
}
run 9r-32~8p-32
run 9r-32~7s-32
run 8p-32~7s-32
echo "$(date -u +%FT%TZ) done" | tee -a "$OUT/job.log"
