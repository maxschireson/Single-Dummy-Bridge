#!/usr/bin/env bash
# The arena's boards for round 4 (Max, 05:31 UTC on 14 November: "What about arena boards? Can you use some of them from the
# gen 9 arena?"), as rows for round2.sh's EXTRA:  round4_arena.sh OUT_DIR LOOP_BOARDS
# 1. Fetches the feeds below read-only (they are never merged) and takes every record not already among rollout net v2's
#    training or validation episodes (~/work/plan/rnet2w/eps and epsB, which are named by git blob, as the feeds' files are).
# 2. BEN (Max, 06:22 UTC: "keep the Ben mix about the same since that is who we are going to grade against"): records with
#    BEN at the table are kept at random up to SHARE (default 0.017, round 3's share of deals with BEN) of all the round's
#    new boards: the arena's other records plus LOOP_BOARDS, the loop's own new tables (which have no BEN).
# 3. Builds rows as rows.sh does (policy-only, the search's or the rollouts' values, alias.txt), with the arena's ids read
#    so: 8p-32 as 8s-32 (Gen 8 card play), stu3-ps as stup0 (Stu); 9a-32 (Gen 9) and 8x3-32 (an 8X variant) keep their own
#    ids, which round2.sh starts from 8s-32's vectors (INIT_AS).
# Writes OUT_DIR/arena.npz and OUT_DIR/arena.log (SKIP_BUILD=1: steps 1 and 2 only). Seed 131's deals (the gate's) are not in any arena feed.
set -euo pipefail
OUT=$1; LOOP_BOARDS=${2:-0}; SHARE=${SHARE:-0.017}; WORKERS=${WORKERS:-6}
W=$HOME/work/loop; PY=$W/venv/bin/python; HERE=$(cd "$(dirname "$0")" && pwd); V2=$HOME/work/plan/rnet2w
FEEDS=${FEEDS:-"arena-gen9-azure4-feed arena-gen9-azure4-ben64-feed arena-gen9-genx-stu-azure4-feed arena-gen8-19bbdce5-20261112-feed
  arena-gen8-independent-feed arena-gen8-candidate-codex-20261112-feed arena-gen8-x3-azure1-feed arena-gen8-azure1-feed
  arena-gen8-azure6-feed arena-gen8-m1-azure1-feed arena-gen8-s1-azure1-feed arena-gen8-s3-azure1-feed arena-gen8-s7-azure1-feed"}
SCORER=models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz
mkdir -p "$OUT/eps" "$OUT/ben"; G=$W/in/arena-git; [ -d "$G/.git" ] || git init -q "$G"
say() { echo "$(date -u +%FT%TZ) $*" | tee -a "$OUT/arena.log"; }
( ls "$V2/eps"; ls "$V2/epsB" ) 2>/dev/null | sed 's/\.json\.gz$//' | sort -u > "$OUT/v2.txt"
say "v2's episodes: $(wc -l < "$OUT/v2.txt")"
: > "$OUT/list.txt"
for f in $FEEDS; do
  # "+": a feed that has moved on since an earlier fetch is no fast-forward of a depth-1 ref (the fetch of 12:04 UTC failed so)
  git -C "$G" fetch -q --depth 1 https://github.com/maxschireson/Single-Dummy-Bridge "+$f:refs/f/$f" || { say "$f: fetch failed"; continue; }
  git -C "$G" ls-tree -r "refs/f/$f" | awk '$4 ~ /\.json\.gz$/ {print $3}' | sort -u > "$OUT/$f.txt"
  comm -23 "$OUT/$f.txt" "$OUT/v2.txt" | sed "s#\$# $f#" >> "$OUT/list.txt"
  say "$f: $(wc -l < "$OUT/$f.txt") records, $(comm -23 "$OUT/$f.txt" "$OUT/v2.txt" | wc -l) not in v2's set"
done
sort -u -k1,1 "$OUT/list.txt" > "$OUT/new.txt"
while read -r blob feed; do
  [ -e "$OUT/eps/$blob.json.gz" ] || [ -e "$OUT/ben/$blob.json.gz" ] || git -C "$G" cat-file blob "$blob" > "$OUT/eps/$blob.json.gz"
done < "$OUT/new.txt"
# BEN at the table: aside, then back at random up to the share
"$PY" - "$OUT" "$LOOP_BOARDS" "$SHARE" <<'PY' | tee -a "$OUT/arena.log"
import glob, gzip, json, os, random, sys
out, loop, share = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
ben, other = [], 0
for f in sorted(glob.glob(f'{out}/eps/*.json.gz')):
    d = json.load(gzip.open(f, 'rt'))
    if any('ben' in str(d.get(k, '')).lower() for k in ('candidate', 'opponent')):
        ben.append(f)
    else:
        other += 1
keep = min(len(ben), int(share * (other + loop) / (1 - share)))
random.Random(4).shuffle(ben)
for f in ben[keep:]:
    os.replace(f, f'{out}/ben/' + os.path.basename(f))
print(f'records without BEN {other}; with BEN {len(ben)}, kept {keep} (share {share} of {other + loop + keep} new boards with the loop\'s {loop})')
PY
[ "${SKIP_BUILD:-0}" = 1 ] && { say "SKIP_BUILD: records selected, no rows built"; exit 0; }
ALIAS="$(cat "$HERE/alias.txt"),8p-32=8s-32,stu3-ps=stup0"
cd "$HERE/../.."
nice -n 10 "$PY" scripts/gen7_build_dataset.py --episodes "$OUT/eps" --scorer "$SCORER" --out "$OUT/arena.npz" --workers "$WORKERS" --policy-only \
  --rollout-gap --alias "$ALIAS" 2>&1 | tail -n 1 | tee -a "$OUT/arena.log"
"$PY" - "$OUT/arena.npz" <<'PY' | tee -a "$OUT/arena.log"
import sys, numpy as np
z = np.load(sys.argv[1], allow_pickle=True)
names = [str(x) for x in z['bot_names']]; meta = z['meta']; cols = [str(x) for x in z['meta_columns']]
b = meta[:, cols.index('bot_name')].astype(int)
print('rows', len(b), '| by deciding bot:', ', '.join(f'{names[i]} {int((b == i).sum())}' for i in np.argsort(-np.bincount(b[b >= 0], minlength=len(names))) if (b == i).any()))
PY
say "arena rows: $OUT/arena.npz"
