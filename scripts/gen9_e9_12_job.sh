#!/usr/bin/env bash
# E9-12 on a box (team/gen9 experiments/E9-12.md): played boards on auctions from a book bid by the rule bidder,
# Gen 9 readers against 8p-32. Run from the repository root of feature/gen9-bidding-cards (or a merge of it).
#
#   SRC=~/capsule/recovery OUT=~/runs/e9-12 WORKERS=8 bash scripts/gen9_e9_12_job.sh
#
# The books are committed (reports/gen9-e9-12-2026-11-12/book-*.json.gz, bid with bridge_harness/rule_bidder.py
# sha256 f03afb2c...), so the auctions do not depend on the rule bidder on the box. Pairs run in order of
# priority; each is resumable (gen8_match.py resumes from its results.jsonl), so the job can be stopped and rerun.
set -euo pipefail
SRC=${SRC:-$HOME/capsule/recovery}
OUT=${OUT:-$HOME/runs/e9-12}
W=${WORKERS:-$(nproc)}
N=${N:-1200}          # main pairs, precision book
NS=${NS:-600}         # slices
BOOKS=reports/gen9-e9-12-2026-11-12
BOTS=configs/gen9-bidding-bots.json
mkdir -p "$OUT"
run() {               # pair seed boards book
  echo "$(date -u +%FT%TZ) start $1 ($3 boards)" | tee -a "$OUT/job.log"
  BRIDGE_DDS_CACHE= python3 scripts/gen9_match.py --source "$SRC" --bots "$BOTS" --pair "$1" --deals "$3" --seed "$2" \
    --workers "$W" --book "$4" --out "$OUT/$1-$2" 2>&1 | tail -3 | tee -a "$OUT/job.log"
}
run 9c-32~8p-32  9121 "$N"  $BOOKS/book-precision-9121.json.gz
run 9x-32~8p-32  9121 "$N"  $BOOKS/book-precision-9121.json.gz
run 9u-32~8p-32  9121 "$NS" $BOOKS/book-precision-9121.json.gz
run 9cs-32~8p-32 9122 "$NS" $BOOKS/book-standard-9122.json.gz
run 9xs-32~8p-32 9122 "$NS" $BOOKS/book-standard-9122.json.gz
run 9u-32~8p-32  9122 "$NS" $BOOKS/book-standard-9122.json.gz
echo "$(date -u +%FT%TZ) done" | tee -a "$OUT/job.log"
