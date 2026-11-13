#!/usr/bin/env bash
# Fetches other collecting boxes' published rows (rows.sh blocks on their transfer branches) into
# ~/work/loop/in/rows-BOX/, a block once:  fetch_rows.sh BOX [BOX ...]
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
done
