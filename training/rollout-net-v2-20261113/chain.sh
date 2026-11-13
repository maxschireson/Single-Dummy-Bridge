#!/bin/bash
# Rollout net v2 on one 8-core box (plan session, queue job `rnet2`), after rollout net v1 (same box, $P/rnet1):
#   fetch every episode on v4.1's feeds and on every Gen 7 and Gen 8 feed that v1's fetch does not already have;
#   build one set from all of them with every bot's decisions (policy-only rows included) and the bots' ids;
#   fetch again for a held-out set of boards that arrived meanwhile (deals in the training set dropped);
#   train 768 wide for 5 epochs from scratch on every deal (v4.1's 768x5 recipe) with the bot vectors;
#   score it against v4.1 and v1's nets on the held-out boards, and push nets, scores and logs.
#   bash training/rollout-net-v2-20261113/chain.sh            (from the repository root; $P is ~/work/plan)
set -uo pipefail
P=${P:-$HOME/work/plan}; PY=${PY:-$HOME/work/venv/bin/python}
T=training/rollout-net-v2-20261113; W=$P/rnet2
SCORER=${SCORER:-$HOME/work/sdb-gen7/models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz}
V41=models/cardplay/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz
FEEDS=('arena-gen6-*' 'arena-gen7-*' 'arena-gen8-*' 'transfer/pre7-test-azure*-20261112')
SHARDS=${SHARDS:-16}
LIMIT=${LIMIT:+--limit $LIMIT}; WIDTH=${WIDTH:-768}; EPOCHS=${EPOCHS:-5}       # LIMIT, WIDTH, EPOCHS, NOPUSH: for a test run
mkdir -p "$W/logs" "$W/data"
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$W/logs/timeline.log"; }
stop() { log "STOPPED: $*"; exit 1; }

log "start; source $(git rev-parse --short HEAD)"
[ -f "$SCORER" ] || stop "no scorer at $SCORER"
[ -d "$P/rnet1/eps" ] || stop "no v1 episodes at $P/rnet1/eps"
PYTHONPATH=$P/pylib "$PY" -c "import jax, optax" 2>/dev/null || stop "jax/optax missing in $P/pylib (v1's chain installs them)"
df -h "$HOME" | tail -1 | tee -a "$W/logs/timeline.log"

# 1. What v1's fetch lacks, from v4.1's feeds and every Gen 7 / Gen 8 feed (one file per blob).
"$PY" $T/fetch_feeds.py --out "$W/eps" --work "$W/git" --manifest "$W/data/fetch.json" --seen "$P/rnet1/eps" --jobs 8 $LIMIT "${FEEDS[@]}" \
  > "$W/logs/fetch.log" 2>&1 || stop "fetch failed"
log "fetched $(ls "$W/eps" | wc -l) more episodes; with v1's $(ls "$P/rnet1/eps" | wc -l)"

# 2. The set: every decision with more than one legal card, every bot, in $SHARDS parts, joined.
d=$W/shards; rm -rf "$d"; mkdir -p "$d"
"$PY" - "$d" "$SHARDS" "$P/rnet1/eps" "$W/eps" <<'PYS'
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
for s in $(ls "$d" | grep -v npz); do
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 "$PY" scripts/gen7_build_dataset.py --episodes "$d/$s" --scorer "$SCORER" --policy-only \
    --out "$d/$s.npz" --workers 8 >> "$W/logs/build.log" 2>&1 || stop "build $s failed"
  log "built $s: $(tail -1 "$W/logs/build.log" | cut -c1-200)"
done
"$PY" $T/merge_sets.py "$W/data/train.npz" "$d"/s*.npz >> "$W/logs/build.log" 2>&1 || stop "merge failed"
log "set: $(tail -1 "$W/logs/build.log" | cut -c1-600)"
rm -rf "$d"

# 3. Held out: boards that reached the feeds since step 1, minus deals the set has.
"$PY" $T/fetch_feeds.py --out "$W/epsB" --work "$W/git" --manifest "$W/data/fetchB.json" --seen "$P/rnet1/eps" --seen "$W/eps" --jobs 8 $LIMIT \
  "${FEEDS[@]}" > "$W/logs/fetchB.log" 2>&1 || stop "fetch B failed"
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 "$PY" scripts/gen7_build_dataset.py --episodes "$W/epsB" --scorer "$SCORER" --policy-only \
  --out "$W/data/freshB_raw.npz" --workers 8 > "$W/logs/buildB.log" 2>&1 || stop "build B failed"
"$PY" $T/fresh_set.py "$W/data/freshB_raw.npz" "$W/data/freshB.npz" "$W/data/train.npz" > "$W/logs/freshB.log" 2>&1 || stop "fresh B failed"
log "freshB: $(cat "$W/logs/freshB.log")"

# 4. Train: 768 wide, 5 epochs from random weights, the rate falling over the whole run; every deal of the set.
unset OMP_NUM_THREADS OPENBLAS_NUM_THREADS MKL_NUM_THREADS
cmp=(--compare "$V41")
for n in ft scratch; do [ -f "$P/rnet1/$n/policy.npz" ] && cmp+=(--compare "$P/rnet1/$n/policy.npz"); done
log "w768 start"
PYTHONPATH=$P/pylib "$PY" scripts/train_rollout_net.py --data "$W/data/train.npz" --all-train --val-data "$W/data/freshB.npz" \
  --kind suit --width $WIDTH --epochs $EPOCHS --id-dropout 0.15 --save-epochs --out "$W/w768" "${cmp[@]}" \
  > "$W/logs/w768.out" 2> "$W/logs/w768.err" || stop "w768 FAILED: $(tail -2 "$W/logs/w768.err")"
cp -f "$W/w768/metrics.json" "$P/runs/rnet2_w768_metrics.json"
log "w768 done: $(tail -1 "$W/logs/w768.out" | cut -c1-400)"

[ -n "${NOPUSH:-}" ] && { log "no push (NOPUSH); end"; exit 0; }
# 5. Push the nets, scores and logs (the set is not kept; the fetch manifests and the builder rebuild it).
BR=transfer/rollout-net-v2-20261113; D=$W/pub
export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
rm -rf "$D"; git init -q "$D"; git -C "$D" checkout -q --orphan "$BR"
mkdir -p "$D/runs/w768"; cp -f "$W"/data/fetch*.json "$D/"; cp -rf "$W/logs" "$D/"
cp -f "$W/w768"/*.npz "$W/w768/metrics.json" "$D/runs/w768/"
printf '# Rollout net v2: training outputs\n\nResearch data, not a feed; never merge. Made by `training/rollout-net-v2-20261113/chain.sh` on\n`research/plan-leverage-g8-20261112` (source in logs/timeline.log). `runs/w768`: policy.npz (the epoch with the best held-out\nlog-loss) and every epoch'"'"'s weights; scores, temperatures and the other nets'"'"' scores on the same rows in metrics.json.\n' > "$D/README.md"
git -C "$D" add -A
git -C "$D" -c user.name="plan box" -c user.email=noreply@anthropic.com commit -q -m "Rollout net v2: nets, scores and logs" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01N2EvxETgngTN3WCMv4MhwW"
git -C "$D" remote add origin ssh://git@github.com/maxschireson/Single-Dummy-Bridge.git
git -C "$D" push -q origin "$BR" 2>&1 | tail -1
log "pushed to $BR; end"
