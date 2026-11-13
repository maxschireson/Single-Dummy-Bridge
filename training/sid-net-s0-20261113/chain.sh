#!/bin/bash
# SiD net S_0 on one 8-core box (sidnet session): steps 1 and 2 of experiments/sid_loop/SPEC.md.
#   fetch      every episode at the feed tips rollout net v2 was built from (v2-fetch.json: 75,545 episodes)
#   label      exact SiD labels for every kept decision with $CARDS or fewer cards (scripts/sid_label.py)
#   fetchB     boards that reached the same feeds since those tips (held out), at most $LIMITB episodes
#   labelB     their labels, in full (every card, also where another card guarantees the target)
#   build      the training set with the labels joined (scripts/gen7_build_dataset.py --labels), in parts, merged
#   buildB     the held-out set, deals of the training set dropped
#   train      S_0: rollout net v2 plus the label heads, --init from v2, v2's recipe
#   e1         student against solver on the held-out boards
#   push       nets, scores, logs, manifests and the labels to transfer/sid-net-s0-20261113
#   STAGES="fetch label" bash training/sid-net-s0-20261113/chain.sh      (from the repository root; default: all)
# Every stage leaves a marker in $W/done and is skipped when it is there; a stopped label stage resumes by episode.
set -uo pipefail
W=${W:-$HOME/work/sidnet}; PY=${PY:-$HOME/work/venv/bin/python}; T=training/sid-net-s0-20261113; V2T=training/rollout-net-v2-20261113
SCORER=${SCORER:-$W/models/hand_fit_v0.npz}; CELLS=${CELLS:-$W/bin/cells}; V2=${V2:-$W/models/rollout_v2_w768_epoch5.npz}
CARDS=${CARDS:-7}; WORKERS=${WORKERS:-8}; LIMITB=${LIMITB:-4000}; SHARDS=${SHARDS:-16}; WIDTH=${WIDTH:-768}; EPOCHS=${EPOCHS:-5}; LR=${LR:-2e-3}
VALDEALS=${VALDEALS:-600}                # held-out deals the trainer scores every epoch on; E1 uses all of them
STAGES=${STAGES:-fetch label fetchB labelB build buildB train e1 push}
FEEDS=('arena-gen6-*' 'arena-gen7-*' 'arena-gen71-*' 'arena-gen8-*' 'arena-gen5rz*' 'transfer/pre7-test-azure*-20261112')
mkdir -p "$W/logs" "$W/data" "$W/done"
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$W/logs/timeline.log"; }
stop() { log "STOPPED: $*"; exit 1; }
want() { [[ " $STAGES " == *" $1 "* ]] && [ ! -f "$W/done/$1" ]; }
log "start; source $(git rev-parse --short HEAD); stages: $STAGES"
[ -f "$SCORER" ] || stop "no scorer at $SCORER"; [ -x "$CELLS" ] || stop "no solver at $CELLS"

if want fetch; then
  "$PY" $T/fetch_tips.py --tips $T/v2-fetch.json --out "$W/eps" --work "$W/git" --manifest "$W/data/fetch.json" --jobs 8 \
    > "$W/logs/fetch.log" 2>&1 || stop "fetch failed: $(tail -2 "$W/logs/fetch.log")"
  log "fetch: $(ls "$W/eps" | wc -l) episodes; $(tail -1 "$W/logs/fetch.log")"; touch "$W/done/fetch"
fi
if want label; then
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 "$PY" scripts/sid_label.py --episodes "$W/eps" --out "$W/labels" --cells "$CELLS" --scorer "$SCORER" \
    --cards "$CARDS" --workers "$WORKERS" >> "$W/logs/label.log" 2>&1 || stop "label failed: $(tail -2 "$W/logs/label.log")"
  log "label: $(tail -1 "$W/logs/label.log")"; touch "$W/done/label"
fi
if want fetchB; then
  "$PY" $V2T/fetch_feeds.py --out "$W/epsB" --work "$W/git" --manifest "$W/data/fetchB.json" --seen "$W/eps" --jobs 8 --limit "$LIMITB" \
    "${FEEDS[@]}" > "$W/logs/fetchB.log" 2>&1 || stop "fetch B failed: $(tail -2 "$W/logs/fetchB.log")"
  log "fetchB: $(ls "$W/epsB" | wc -l) episodes; $(tail -1 "$W/logs/fetchB.log")"; touch "$W/done/fetchB"
fi
if want labelB; then
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 "$PY" scripts/sid_label.py --episodes "$W/epsB" --out "$W/labelsB" --cells "$CELLS" --scorer "$SCORER" \
    --cards "$CARDS" --workers "$WORKERS" --full >> "$W/logs/labelB.log" 2>&1 || stop "label B failed: $(tail -2 "$W/logs/labelB.log")"
  log "labelB: $(tail -1 "$W/logs/labelB.log")"; touch "$W/done/labelB"
fi
for STAGE in build buildB train e1 push; do         # STAGE, not a name a sourced stage file might use (s was: stage-build's loop
  if want $STAGE; then                               # over parts overwrote it, and build's marker was written as done/s15)
    case $STAGE in                          # a stage never runs on an earlier stage's partial output
      build) [ -f "$W/done/label" ] || stop "build needs the label stage finished";;
      buildB) [ -f "$W/done/labelB" ] && [ -f "$W/done/build" ] || stop "buildB needs labelB and build finished";;
      train) [ -f "$W/done/buildB" ] || stop "train needs buildB finished";;
      e1) [ -f "$W/done/train" ] || stop "e1 needs train finished";;
    esac
    [ -f $T/stage-$STAGE.sh ] || stop "stage $STAGE is not written yet at this source"
    . $T/stage-$STAGE.sh || stop "stage $STAGE failed"
    touch "$W/done/$STAGE"
  fi
done
log "end of stages: $STAGES"
