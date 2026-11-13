#!/usr/bin/env bash
# One match or collection of the rollout loop, run as a systemd unit on a box:
#   run.sh NAME PAIR SEED FIRST DEALS WORKERS [more scripts/x8_match.py options, e.g. --episodes]
# Writes ~/work/loop/runs/NAME (results.jsonl, summary.json, manifest.json, episodes/ with --episodes).
# It resumes: boards already in results.jsonl are skipped (scripts/gen8_match.py), so a restarted unit loses only the
# boards in hand. Deals are a function of (SEED, index): seed 131 is the gate's, never a collection's.
set -euo pipefail
W=$HOME/work/loop; S=$W/src; PY=$W/venv/bin/python
NAME=$1; PAIR=$2; SEED=$3; FIRST=$4; DEALS=$5; WORKERS=$6; shift 6
export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
cd "$S"
echo "$(date -u +%FT%TZ) start $NAME $PAIR seed $SEED first $FIRST deals $DEALS workers $WORKERS $* (source $(git rev-parse --short HEAD))" >> "$W/runs.log"
"$PY" scripts/x8_match.py --source "$W/capsule/recovery" --bots configs/loop-bots.json --pair "$PAIR" --deals "$DEALS" --first "$FIRST" \
  --seed "$SEED" --workers "$WORKERS" --out "$W/runs/$NAME" "$@" >> "$W/runs/$NAME.log" 2>&1 && rc=0 || rc=$?
echo "$(date -u +%FT%TZ) end $NAME: exit $rc" >> "$W/runs.log"
exit $rc
