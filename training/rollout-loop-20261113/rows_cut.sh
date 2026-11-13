#!/usr/bin/env bash
# A round's cut on a collecting box: the boards of each RUN past its last published block, once:  rows_cut.sh RUN [RUN ...]
# rows.sh publishes whole blocks of 1,000 boards, so at a cut up to 999 boards a run are not yet in any block. This
# builds them as rows.sh would (same builder, flags and aliases) into ~/work/loop/pub/rows-cut/RUN-<first>-<last>.npz,
# replacing that run's earlier cut file; the publisher pushes it with the rest of pub/ within ten minutes.
# fetch_rows.sh takes cut files only with CUT=1, and skips one when the run has since published a block from <first> on
# (that block holds the same boards). Runs at Nice 10 on two workers; the collection is not touched.
set -euo pipefail
W=$HOME/work/loop; PY=$W/venv/bin/python; HERE=$(cd "$(dirname "$0")" && pwd); BLOCK=${BLOCK:-1000}
SCORER=models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz
cd "$HERE/../.."; mkdir -p "$W/pub/rows-cut"
for run in "$@"; do
  E=$W/runs/$run/episodes; [ -d "$E" ] || { echo "$run: no episodes"; continue; }
  find "$E" -name '*.json.gz' -mmin +1 -printf '%f\n' | sed 's/\..*//' | sort -n > "$W/cut-$run.txt"
  [ -s "$W/cut-$run.txt" ] || { echo "$run: no finished boards"; continue; }
  start=$(head -n 1 "$W/cut-$run.txt" | awk '{print $1 + 0}')
  for f in "$W"/pub/rows/"$run"-*.npz; do
    [ -e "$f" ] || continue
    b=$(basename "$f" .npz); b=${b##*-}; [ $((b + BLOCK)) -gt "$start" ] && start=$((b + BLOCK))
  done
  awk -v a="$start" '$1 + 0 >= a' "$W/cut-$run.txt" > "$W/cut-$run.sel"
  n=$(wc -l < "$W/cut-$run.sel")
  [ "$n" -gt 0 ] || { echo "$run: nothing past block end $start"; continue; }
  last=$(tail -n 1 "$W/cut-$run.sel" | awk '{print $1 + 0}')
  D=$(mktemp -d "$W/cut-tmp.XXXX"); mkdir "$D/eps"
  while read -r i; do ln "$E/$i.json.gz" "$D/eps/" 2>/dev/null || ln "$E/$(printf '%06d' "$i").json.gz" "$D/eps/"; done < "$W/cut-$run.sel"
  if nice -n 10 "$PY" scripts/gen7_build_dataset.py --episodes "$D/eps" --scorer "$SCORER" --out "$D/rows.npz" --workers 2 --policy-only \
       --rollout-gap --alias "$(cat "$HERE/alias.txt")" > "$D/build.log" 2>&1 \
     && "$PY" -c "import numpy as np, sys; z = np.load(sys.argv[1], allow_pickle=True); np.savez_compressed(sys.argv[2], **{k: z[k] for k in z.files})" "$D/rows.npz" "$D/small.npz"; then
    rm -f "$W"/pub/rows-cut/"$run"-*.npz
    mv "$D/small.npz" "$W/pub/rows-cut/$run-$start-$last.npz"
    echo "$(date -u +%FT%TZ) cut $run $start-$last: $n boards, $(tail -n 1 "$D/build.log" | cut -c1-120), $(du -k "$W/pub/rows-cut/$run-$start-$last.npz" | cut -f1) KB" | tee -a "$W/pub/rows-cut/cut.log"
  else
    echo "$(date -u +%FT%TZ) cut $run $start-$last failed: $(tail -n 2 "$D/build.log" | tr '\n' ' ' | cut -c1-200)" | tee -a "$W/pub/rows-cut/cut.log"
  fi
  rm -rf "$D" "$W/cut-$run.sel"
done
