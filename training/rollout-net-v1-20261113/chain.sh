#!/bin/bash
# Rollout net v1 on one 8-core box (plan session, queue job `rnet1`): fetch every episode of the Gen 7 and Gen 8 feeds,
# build the set from the decisions of the Gen 7+ bots only, fine-tune v4.1 on it, train the same net from scratch for
# comparison, score both and v4.1 on the held-out deals, and push the nets and their scores.
#   bash training/rollout-net-v1-20261113/chain.sh            (from the repository root; $P is ~/work/plan)
set -uo pipefail
P=${P:-$HOME/work/plan}; PY=${PY:-$HOME/work/venv/bin/python}
T=training/rollout-net-v1-20261113; W=$P/rnet1
SCORER=${SCORER:-$HOME/work/sdb-gen7/models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz}
V41=models/cardplay/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz
BOTS=7s-32,7f-32,71s-32,8s-32,8c-32
mkdir -p "$W/logs" "$W/data"
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$W/logs/timeline.log"; }
stop() { log "STOPPED: $*"; exit 1; }

log "start; source $(git rev-parse --short HEAD)"
[ -f "$SCORER" ] || stop "no scorer at $SCORER"
if ! PYTHONPATH=$P/pylib "$PY" -c "import jax, optax" 2>/dev/null; then
  "$PY" -m pip install -q --target "$P/pylib" "jax[cpu]" optax > "$W/logs/pip.log" 2>&1 || stop "pip install failed"
fi
PYTHONPATH=$P/pylib "$PY" -c "import jax, optax; print('jax', jax.__version__, 'optax', optax.__version__)" | tee -a "$W/logs/timeline.log"

# 1. Every episode on the 82 Gen 7 and Gen 8 feeds of the dashboard registry (feeds.txt), one file per blob.
"$PY" $T/fetch_feeds.py --out "$W/eps" --work "$W/git" --manifest "$W/data/fetch.json" --jobs 8 $(cat $T/feeds.txt) \
  > "$W/logs/fetch.log" 2>&1 || stop "fetch failed"
log "fetched $(ls "$W/eps" | wc -l) episodes"

# 2. The set: Gen 7+ bots' searched decisions only, built in 4 parts and joined.
d=$W/shards; rm -rf "$d"; mkdir -p "$d"
"$PY" - "$W/eps" "$d" 4 <<'PYS'
import os, sys
from pathlib import Path
eps, d, k = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
files = sorted(eps.glob('*.json.gz'))
for i in range(k):
    (d / f's{i}').mkdir()
    for f in files[i * len(files) // k:(i + 1) * len(files) // k]:
        os.symlink(f, d / f's{i}' / f.name)
PYS
for s in s0 s1 s2 s3; do
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 "$PY" scripts/gen7_build_dataset.py --episodes "$d/$s" --scorer "$SCORER" --bots $BOTS \
    --out "$d/$s.npz" --workers 8 >> "$W/logs/build.log" 2>&1 || stop "build $s failed"
  log "built $s: $(tail -1 "$W/logs/build.log" | cut -c1-200)"
done
"$PY" $T/merge_sets.py "$W/data/train.npz" "$d"/s*.npz >> "$W/logs/build.log" 2>&1 || stop "merge failed"
log "set: $(tail -1 "$W/logs/build.log" | cut -c1-300)"
rm -rf "$d"

# 3. Train. Deals split by family hash: 80% train, 10% validation (epoch choice), 10% test.
unset OMP_NUM_THREADS OPENBLAS_NUM_THREADS MKL_NUM_THREADS
run() {   # run NAME ARGS...
  local name=$1; shift
  log "$name start"
  PYTHONPATH=$P/pylib "$PY" scripts/train_gen7_policy.py --data "$W/data/train.npz" --out "$W/$name" --kind suit --width 512 \
    --compare $V41 "$@" > "$W/logs/$name.out" 2> "$W/logs/$name.err" || { log "$name FAILED: $(tail -2 "$W/logs/$name.err")"; return 1; }
  cp -f "$W/$name/metrics.json" "$P/runs/rnet1_${name}_metrics.json"
  log "$name done: $(tail -1 "$W/logs/$name.out" | cut -c1-300)"
}
run ft --epochs 4 --lr 5e-4 --init $V41          # v4.1 fine-tuned on Gen 7+ play
run scratch --epochs 6 --lr 2e-3                  # the same data from random weights, for comparison
cp -f "$W"/logs/*.log "$W"/logs/*.out "$P/runs/" 2>/dev/null

# 4. Push the nets, scores and logs (the 2-3 GB set is not kept; the fetch manifest and the builder rebuild it).
BR=transfer/rollout-net-v1-20261113; D=$W/pub
export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
rm -rf "$D"; git init -q "$D"; git -C "$D" checkout -q --orphan "$BR"
mkdir -p "$D/runs"; cp -f "$W/data/fetch.json" "$D/"; cp -rf "$W/logs" "$D/"
for n in ft scratch; do [ -d "$W/$n" ] && mkdir -p "$D/runs/$n" && cp -f "$W/$n"/policy.npz "$W/$n"/metrics.json "$D/runs/$n/"; done
printf '# Rollout net v1: training outputs\n\nResearch data, not a feed; never merge. Made by `training/rollout-net-v1-20261113/chain.sh` on\n`research/plan-leverage-g8-20261112` (source in logs/timeline.log). `runs/ft`: v4.1 fine-tuned on the Gen 7+ bots'"'"' play;\n`runs/scratch`: the same from random weights. Scores in each metrics.json, v4.1 on the same rows under `compared`.\n' > "$D/README.md"
git -C "$D" add -A
git -C "$D" -c user.name="plan box" -c user.email=noreply@anthropic.com commit -q -m "Rollout net v1: nets, scores and logs" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01N2EvxETgngTN3WCMv4MhwW"
git -C "$D" remote add origin ssh://git@github.com/maxschireson/Single-Dummy-Bridge.git
git -C "$D" push -q origin "$BR" 2>&1 | tail -1
log "pushed to $BR; end"
