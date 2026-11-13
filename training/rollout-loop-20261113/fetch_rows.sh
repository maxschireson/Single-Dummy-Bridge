#!/usr/bin/env bash
# Fetches other collecting boxes' published rows (rows.sh blocks on their transfer branches) into
# ~/work/loop/in/rows-BOX/, a block once:  fetch_rows.sh BOX [BOX ...]
# CUT=1: also each run's latest cut file (rows_cut.sh) into ~/work/loop/in/cut-BOX/ (replacing the earlier ones), unless
# the run has since published a block that starts at or after the cut's first board.
set -euo pipefail
W=$HOME/work/loop
for box in "$@"; do
  D=$W/in/git-$box; mkdir -p "$W/in/rows-$box"
  [ -d "$D/.git" ] || git init -q "$D"
  git -C "$D" fetch -q --depth 1 https://github.com/maxschireson/Single-Dummy-Bridge "transfer/rollout-loop-$box-20261113"
  for f in $(git -C "$D" ls-tree --name-only FETCH_HEAD rows/ | grep '\.npz$' || true); do
    [ -e "$W/in/rows-$box/$(basename "$f")" ] || git -C "$D" show "FETCH_HEAD:$f" > "$W/in/rows-$box/$(basename "$f")"
  done
  echo "$box: $(ls "$W/in/rows-$box" | wc -l) row files, $(du -sm "$W/in/rows-$box" | cut -f1) MB"
  if [ "${CUT:-0}" = 1 ]; then
    rm -rf "$W/in/cut-$box"; mkdir -p "$W/in/cut-$box"
    blocks=$(git -C "$D" ls-tree --name-only FETCH_HEAD rows/ | grep '\.npz$' || true)
    for f in $(git -C "$D" ls-tree --name-only FETCH_HEAD rows-cut/ 2>/dev/null | grep '\.npz$' || true); do
      b=$(basename "$f" .npz); last=${b##*-}; b=${b%-*}; first=${b##*-}; run=${b%-*}
      if echo "$blocks" | sed -n "s#^rows/$run-\([0-9]*\)\.npz\$#\1#p" | awk -v a="$first" '$1 + 0 >= a + 0 {f = 1} END {exit !f}'; then
        echo "$box: cut $(basename "$f") skipped, a block from $first on is published"
      else
        git -C "$D" show "FETCH_HEAD:$f" > "$W/in/cut-$box/$(basename "$f")"; echo "$box: cut $(basename "$f")"
      fi
    done
  fi
done
