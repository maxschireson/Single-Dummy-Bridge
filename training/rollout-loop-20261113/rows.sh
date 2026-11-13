#!/usr/bin/env bash
# A collecting box's training rows, for a trainer on another box:  rows.sh RUN [RUN ...]
# For each RUN under ~/work/loop/runs, every block of BLOCK board indices (1,000) whose boards are all played becomes
# one compressed file ~/work/loop/pub/rows/RUN-<first index of the block>.npz, written once and never changed; the
# publisher pushes it with the rest of pub/. A block with a board or two missing (a failed board) is written once the
# run is 200 boards past it. Rows are scripts/gen7_build_dataset.py's with the rollouts' values (--rollout-gap) and the
# ids of alias.txt, as round2.sh builds them. Loops every ten minutes, at Nice 10 on two workers.
set -uo pipefail
W=$HOME/work/loop; PY=$W/venv/bin/python; HERE=$(cd "$(dirname "$0")" && pwd); BLOCK=${BLOCK:-1000}
SCORER=models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz
cd "$HERE/../.."; mkdir -p "$W/pub/rows"
while :; do
  for run in "$@"; do
    E=$W/runs/$run/episodes; [ -d "$E" ] || continue
    find "$E" -name '*.json.gz' -mmin +1 -printf '%f\n' | sed 's/\..*//' | sort -n > "$W/rows-$run.txt"
    [ -s "$W/rows-$run.txt" ] || continue
    lo=$(head -n 1 "$W/rows-$run.txt" | sed 's/^0*//'); hi=$(tail -n 1 "$W/rows-$run.txt" | sed 's/^0*//'); lo=${lo:-0}; hi=${hi:-0}
    start=$((lo / BLOCK * BLOCK))
    while [ $((start + BLOCK)) -le $((hi + 1)) ]; do
      out=$W/pub/rows/$run-$start.npz
      if [ ! -e "$out" ]; then
        n=$(awk -v a="$start" -v b="$((start + BLOCK))" '$1 + 0 >= a && $1 + 0 < b' "$W/rows-$run.txt" | wc -l)
        first=$((lo > start ? lo : start))
        if [ "$n" -ge $((start + BLOCK - first)) ] || { [ "$hi" -ge $((start + BLOCK + 200)) ] && [ "$n" -ge $((start + BLOCK - first - 3)) ]; }; then
          D=$(mktemp -d "$W/rows-tmp.XXXX"); mkdir "$D/eps"
          awk -v a="$start" -v b="$((start + BLOCK))" '$1 + 0 >= a && $1 + 0 < b' "$W/rows-$run.txt" | while read -r i; do ln "$E"/"$i".json.gz "$D/eps/" 2>/dev/null || ln "$E"/$(printf '%06d' "$i").json.gz "$D/eps/"; done
          if nice -n 10 "$PY" scripts/gen7_build_dataset.py --episodes "$D/eps" --scorer "$SCORER" --out "$D/rows.npz" --workers 2 --policy-only \
               --rollout-gap --alias "$(cat "$HERE/alias.txt")" > "$D/build.log" 2>&1 \
             && "$PY" -c "import numpy as np, sys; z = np.load(sys.argv[1], allow_pickle=True); np.savez_compressed(sys.argv[2], **{k: z[k] for k in z.files})" "$D/rows.npz" "$D/small.npz"; then
            mv "$D/small.npz" "$out"
            echo "$(date -u +%FT%TZ) rows $run block $start: $n boards, $(tail -n 1 "$D/build.log" | cut -c1-120), $(du -k "$out" | cut -f1) KB" >> "$W/rows.log"
          else
            echo "$(date -u +%FT%TZ) rows $run block $start failed: $(tail -n 2 "$D/build.log" | tr '\n' ' ' | cut -c1-200)" >> "$W/rows.log"
          fi
          rm -rf "$D"
        fi
      fi
      start=$((start + BLOCK))
    done
  done
  cp -f "$W/rows.log" "$W/pub/rows/rows.log" 2>/dev/null
  sleep 600
done
