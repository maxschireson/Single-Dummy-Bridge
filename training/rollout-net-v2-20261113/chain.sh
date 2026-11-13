#!/bin/bash
# Rollout net v2 on one 8-core box (plan session, queue job `rnet2`), after rollout net v1 (same box, $P/rnet1):
#   fetch every episode on v4.1's feeds and on every Gen 7 and Gen 8 feed that v1's fetch does not already have;
#   build one set from all of them with every bot's decisions (policy-only rows included) and the bots' ids;
#   fetch again for a held-out set of boards that arrived meanwhile (deals in the training set dropped);
#   train 768 wide for 5 epochs from scratch on every deal (v4.1's 768x5 recipe) with the bot vectors;
#   score it against v4.1 and v1's nets on the held-out boards, and push nets, scores and logs.
#   bash training/rollout-net-v2-20261113/chain.sh            (from the repository root; $P is ~/work/plan)
# Warm start on another box (no v1 episodes there: everything is fetched):
#   W=$P/rnet2w RUN=warm INIT=<768-wide net> LR=5e-4 EPOCHS=3 BRANCH=transfer/rollout-net-v2w-20261113 bash .../chain.sh
set -uo pipefail
P=${P:-$HOME/work/plan}; PY=${PY:-$HOME/work/venv/bin/python}
T=training/rollout-net-v2-20261113; W=${W:-$P/rnet2}; RUN=${RUN:-w768}; INIT=${INIT:-}; LR=${LR:-2e-3}
BRANCH=${BRANCH:-transfer/rollout-net-v2-20261113}; V1=$P/rnet1/eps
SCORER=${SCORER:-$HOME/work/sdb-gen7/models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz}
V41=models/cardplay/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz
FEEDS=('arena-gen6-*' 'arena-gen7-*' 'arena-gen71-*' 'arena-gen8-*' 'arena-gen5rz*' 'transfer/pre7-test-azure*-20261112')
# RESUME=1: a run stopped before training picks up its fetch, parts and set; what the fetch brings now (new feeds or
# boards) is built as one more part and joined in.
SHARDS=${SHARDS:-16}
LIMIT=${LIMIT:+--limit $LIMIT}; WIDTH=${WIDTH:-768}; EPOCHS=${EPOCHS:-5}       # LIMIT, WIDTH, EPOCHS, NOPUSH: for a test run
mkdir -p "$W/logs" "$W/data"
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$W/logs/timeline.log"; }
stop() { log "STOPPED: $*"; exit 1; }

log "start; source $(git rev-parse --short HEAD)"
[ -f "$SCORER" ] || stop "no scorer at $SCORER"
SEEN=(); [ -d "$V1" ] && SEEN=(--seen "$V1") || V1=""
if ! PYTHONPATH=$P/pylib "$PY" -c "import jax, optax" 2>/dev/null; then
  "$PY" -m pip install -q --target "$P/pylib" "jax[cpu]" optax > "$W/logs/pip.log" 2>&1 || stop "pip install failed"
fi
[ -z "$INIT" ] || [ -f "$INIT" ] || stop "no net to start from at $INIT"
df -h "$HOME" | tail -1 | tee -a "$W/logs/timeline.log"

# 1. What v1's fetch lacks, from v4.1's feeds and every Gen 7 / Gen 8 feed (one file per blob).
mkdir -p "$W/eps"; ls "$W/eps" | sort > "$W/data/eps_before.txt"
"$PY" $T/fetch_feeds.py --out "$W/eps" --work "$W/git" --manifest "$W/data/fetch.json" "${SEEN[@]}" --jobs 8 $LIMIT "${FEEDS[@]}" \
  > "$W/logs/fetch.log" 2>&1 || stop "fetch failed"
log "fetched $(ls "$W/eps" | wc -l) episodes${V1:+; with v1 $(ls "$V1" | wc -l)}"
ls "$W/eps" | sort | comm -13 "$W/data/eps_before.txt" - > "$W/data/eps_new.txt"

# 2. The set: every decision with more than one legal card, every bot, in $SHARDS parts, joined.
d=$W/shards; parts=()
if [ -n "${RESUME:-}" ] && [ -f "$W/data/train.npz" ] && grep -q " set: " "$W/logs/timeline.log"; then
  mv "$W/data/train.npz" "$W/data/train_base.npz"; parts=("$W/data/train_base.npz"); log "resume: the joined set so far is one part"
elif [ -n "${RESUME:-}" ] && [ -f "$W/data/train_base.npz" ]; then
  parts=("$W/data/train_base.npz"); log "resume: the joined set so far is one part"
elif [ -n "${RESUME:-}" ] && [ -d "$d" ]; then
  rm -f "$W/data/train.npz"; log "resume: keeping the parts in $d"
else
  rm -rf "$d"; mkdir -p "$d"
  "$PY" - "$d" "$SHARDS" $V1 "$W/eps" <<'PYS'
import os, sys
from pathlib import Path
d, k = Path(sys.argv[1]), int(sys.argv[2])
files = sorted(f for e in sys.argv[3:] for f in Path(e).glob('*.json.gz'))
names = {}
for f in files:
    names.setdefault(f.name, f)          # a blob in both directories once
files = sorted(names.values(), key=lambda f: f.name)
for i in range(k):
    (d / f's{i:02d}').mkdir()
    for f in files[i * len(files) // k:(i + 1) * len(files) // k]:
        os.symlink(f, d / f's{i:02d}' / f.name)
print(len(files), 'episodes in', k, 'parts', flush=True)
PYS
  : > "$W/data/eps_new.txt"           # a fresh split already holds everything fetched
fi
mkdir -p "$d"
if [ -s "$W/data/eps_new.txt" ]; then          # resume: what the fetch just brought, as one more part
  x=sx$(date -u +%H%M%S); mkdir -p "$d/$x"         # a new name each time: an earlier resume's part stays
  while read -r f; do ln -s "$W/eps/$f" "$d/$x/$f"; done < "$W/data/eps_new.txt"
  log "resume: $(wc -l < "$W/data/eps_new.txt") newly fetched episodes as part $x"
fi
for s in $(ls "$d" | grep -v npz); do
  [ -f "$d/$s.npz" ] && continue
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 "$PY" scripts/gen7_build_dataset.py --episodes "$d/$s" --scorer "$SCORER" --policy-only \
    --out "$d/$s.npz.tmp.npz" --workers 8 >> "$W/logs/build.log" 2>&1 || stop "build $s failed"
  mv "$d/$s.npz.tmp.npz" "$d/$s.npz"
  log "built $s: $(tail -1 "$W/logs/build.log" | cut -c1-200)"
done
shopt -s nullglob; parts+=("$d"/s*.npz); shopt -u nullglob
"$PY" $T/merge_sets.py "$W/data/train.npz" "${parts[@]}" >> "$W/logs/build.log" 2>&1 || stop "merge failed"
log "set: $(tail -1 "$W/logs/build.log" | cut -c1-600)"
rm -rf "$d" "$W/data/train_base.npz"

# 3. Held out: boards that reached the feeds since step 1, minus deals the set has.
rm -rf "$W/epsB"
"$PY" $T/fetch_feeds.py --out "$W/epsB" --work "$W/git" --manifest "$W/data/fetchB.json" "${SEEN[@]}" --seen "$W/eps" --jobs 8 $LIMIT \
  "${FEEDS[@]}" > "$W/logs/fetchB.log" 2>&1 || stop "fetch B failed"
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 "$PY" scripts/gen7_build_dataset.py --episodes "$W/epsB" --scorer "$SCORER" --policy-only \
  --out "$W/data/freshB_raw.npz" --workers 8 > "$W/logs/buildB.log" 2>&1 || stop "build B failed"
"$PY" $T/fresh_set.py "$W/data/freshB_raw.npz" "$W/data/freshB.npz" "$W/data/train.npz" > "$W/logs/freshB.log" 2>&1 || stop "fresh B failed"
log "freshB: $(cat "$W/logs/freshB.log")"

# 4. Train: by default 768 wide, 5 epochs from random weights, the rate falling over the whole run; every deal of the set.
unset OMP_NUM_THREADS OPENBLAS_NUM_THREADS MKL_NUM_THREADS
cmp=(--compare "$V41")
for n in ft scratch; do [ -f "$P/rnet1/$n/policy.npz" ] && cmp+=(--compare "$P/rnet1/$n/policy.npz"); done
for f in ${CMP_NETS:-}; do cmp+=(--compare "$f"); done          # other nets to score on the same rows (paths, space-separated)
log "$RUN start${INIT:+ from $INIT} (lr $LR, $EPOCHS epochs)"
PYTHONPATH=$P/pylib "$PY" scripts/train_rollout_net.py --data "$W/data/train.npz" --all-train --val-data "$W/data/freshB.npz" \
  --kind suit --width $WIDTH --epochs $EPOCHS --lr $LR ${INIT:+--init "$INIT"} --id-dropout 0.15 --save-epochs --out "$W/$RUN" "${cmp[@]}" \
  > "$W/logs/$RUN.out" 2> "$W/logs/$RUN.err" || stop "$RUN FAILED: $(tail -2 "$W/logs/$RUN.err")"
mkdir -p "$P/runs"; cp -f "$W/$RUN/metrics.json" "$P/runs/$(basename "$W")_${RUN}_metrics.json"
log "$RUN done: $(tail -1 "$W/logs/$RUN.out" | cut -c1-400)"

[ -n "${NOPUSH:-}" ] && { log "no push (NOPUSH); end"; exit 0; }
# 5. Push the nets, scores and logs (the set is not kept; the fetch manifests and the builder rebuild it).
BR=$BRANCH; D=$W/pub
export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
rm -rf "$D"; git init -q "$D"; git -C "$D" checkout -q --orphan "$BR"
mkdir -p "$D/runs/$RUN"; cp -f "$W"/data/fetch*.json "$D/"; cp -rf "$W/logs" "$D/"
cp -f "$W/$RUN"/*.npz "$W/$RUN/metrics.json" "$D/runs/$RUN/"
printf '# Rollout net v2: training outputs\n\nResearch data, not a feed; never merge. Made by `training/rollout-net-v2-20261113/chain.sh` on\n`research/plan-leverage-g8-20261112` (source and settings in logs/timeline.log). `runs/'"$RUN"'`: policy.npz (the epoch with the best held-out\nlog-loss) and every epoch'"'"'s weights; scores, temperatures and the other nets'"'"' scores on the same rows in metrics.json.\n' > "$D/README.md"
git -C "$D" add -A
git -C "$D" -c user.name="plan box" -c user.email=noreply@anthropic.com commit -q -m "Rollout net v2: nets, scores and logs" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01N2EvxETgngTN3WCMv4MhwW"
git -C "$D" remote add origin ssh://git@github.com/maxschireson/Single-Dummy-Bridge.git
git -C "$D" push -q origin "$BR" 2>&1 | tail -1
log "pushed to $BR; end"
