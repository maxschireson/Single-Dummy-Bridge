#!/bin/bash
# Policy 4.1 on the temporary box, after the first fetch (unit p41-fetch1) has finished:
#   build the training set from every episode fetched (no deal held back);
#   fetch what reached the feeds meanwhile and build it as held-out set B (epoch scores, temperature);
#   train 512 wide; then fetch again for held-out set C (the comparison with v4) while 768 wide trains.
set -uo pipefail
P=$HOME/work/p41; S=$HOME/work/p41src; T=$S/training/policy-v4.1-20261112; PY=$HOME/work/venv/bin/python
SCORER=$HOME/work/repo/models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz
FEEDS=('arena-gen6-*' 'arena-gen7-phase1-*' 'transfer/pre7-test-azure*-20261112')
log() { echo "$1 $(date -u +%T)" >> $P/logs/timeline.log; }
stop() { log "CHAIN STOPPED: $1"; exit 1; }
cd $S
while ! grep -q "fetch1 exit" $P/logs/timeline.log; do sleep 5; done
grep -q "fetch1 exit 0" $P/logs/timeline.log || stop "fetch1 failed"

build_shards() {   # build_shards EPISODE_DIR OUT.npz TAG SHARDS : build in parts so that memory stays small, then join them
  local eps=$1 out=$2 tag=$3 k=$4 d=$P/shards_$3
  rm -rf $d; mkdir -p $d
  $PY - "$eps" "$d" "$k" > $P/logs/build$tag.log 2>&1 <<'PY' || return 1
import os, sys
from pathlib import Path
eps, d, k = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
files = sorted(eps.glob('*.json.gz'))
for i in range(k):
    (d / f's{i:02d}').mkdir()
    for f in files[i * len(files) // k:(i + 1) * len(files) // k]:
        os.symlink(f, d / f's{i:02d}' / f.name)
print(len(files), 'episodes in', k, 'shards', flush=True)
PY
  for s in $(ls $d); do
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 $PY scripts/gen7_build_dataset.py --episodes $d/$s --scorer $SCORER --out $d/$s.npz --workers 8 >> $P/logs/build$tag.log 2>&1 || return 1
    echo "shard $s done $(date -u +%T)" >> $P/logs/build$tag.log
  done
  $PY $T/merge_sets.py $out $d/s*.npz >> $P/logs/build$tag.log 2>&1 || return 1
  rm -rf $d
}
log "buildA start"
build_shards $P/eps $P/data/gen7_v41_train.npz A 16 || stop "buildA failed"
log "buildA done: $(tail -1 $P/logs/buildA.log)"

fresh() {   # fresh NAME SEEN_DIR... : fetch what is new, build it, drop deals the training set has
  local name=$1; shift
  local seen=(); for d in "$@"; do seen+=(--seen "$d"); done
  $PY $T/fetch_feeds.py --out $P/eps$name --work $P/git --manifest $P/data/fetch$name.json "${seen[@]}" --jobs 8 "${FEEDS[@]}" > $P/logs/fetch$name.log 2>&1 || return 1
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 $PY scripts/gen7_build_dataset.py --episodes $P/eps$name --scorer $SCORER --out $P/data/fresh${name}_raw.npz --workers 8 > $P/logs/build$name.log 2>&1 || return 1
  $PY $T/fresh_set.py $P/data/fresh${name}_raw.npz $P/data/fresh$name.npz $P/data/gen7_v41_train.npz > $P/logs/fresh$name.log 2>&1 || return 1
  log "fresh$name done: $(cat $P/logs/fresh$name.log)"
}
fresh B $P/eps || stop "fresh B failed"

train() {   # train WIDTH
  log "w$1 start"
  $PY scripts/train_gen7_policy.py --data $P/data/gen7_v41_train.npz --all-train --val-data $P/data/freshB.npz \
      --kind suit --width $1 --epochs 3 --augment none --save-epochs --out $P/runs/w$1 > $P/logs/w$1.out 2> $P/logs/w$1.err || { log "w$1 FAILED"; return 1; }
  log "w$1 done"
}
train 512 || exit 1
( fresh C $P/eps $P/epsB || log "fresh C failed" ) &
[ -e $P/NO768 ] || train 768
wait
log "chain end"
