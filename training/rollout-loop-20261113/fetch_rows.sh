#!/usr/bin/env bash
# Fetches other collecting boxes' published rows (rows.sh blocks on their transfer branches) into
# ~/work/loop/in/rows-BOX/, a block once:  fetch_rows.sh BOX [BOX ...]
# CUT=1: also each run's latest cut file (rows_cut.sh) into ~/work/loop/in/cut-BOX/ (replacing the earlier ones), unless
# the run has since published a block that starts at or after the cut's first board.
# Every fetched file's bot names are then read through alias.txt (a block built before an alias was added keeps the
# collection's raw ids, e.g. stu0-psa and stu0-psb before 00:40 UTC on 14 November; they become stup0).
set -euo pipefail
W=$HOME/work/loop; HERE=$(cd "$(dirname "$0")" && pwd)
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
"$W/venv/bin/python" - "$(cat "$HERE/alias.txt")" "$@" <<'PY'
import sys, os, glob
import numpy as np
alias = dict(x.split('=', 1) for x in sys.argv[1].strip().split(',') if x)
W = os.path.expanduser('~/work/loop')
for box in sys.argv[2:]:
    for f in sorted(glob.glob(f'{W}/in/rows-{box}/*.npz') + glob.glob(f'{W}/in/cut-{box}/*.npz')):
        with np.load(f, allow_pickle=True) as z:
            names = [str(x) for x in z['bot_names']]
            if not any(n in alias for n in names):
                continue
            d = {k: z[k] for k in z.files}
        d['bot_names'] = np.array([alias.get(n, n) for n in names])
        np.savez_compressed(f + '.tmp.npz', **d)
        os.replace(f + '.tmp.npz', f)
        print(f'{os.path.basename(f)}: bot names read through alias.txt')
PY
