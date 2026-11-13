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
# ~/work/loop/BF16 present: collection runs (names starting sp) play with the nets' forward pass in bf16
# (gen7_net.Bf16Forward, about 2x the net; the first card unchanged on 99.7% of held-out rows). Measurement runs stay fp32.
PREC=fp32
if [ -e "$W/BF16" ]; then case "$NAME" in sp*) export BRIDGE_NET_BF16=1; PREC=bf16 ;; esac; fi
# ~/work/loop/RECYCLE holding a number N: collection runs play in rounds of N boards a worker, each round with fresh worker
# processes (gen8_match --recycle). A worker's memory grows board after board (seen with the nets in bf16) until the box
# runs out and a worker is killed; fresh processes keep it bounded. Play is unchanged.
RECYCLE=()
if [ -s "$W/RECYCLE" ]; then case "$NAME" in sp*) RECYCLE=(--recycle "$(tr -dc 0-9 < "$W/RECYCLE")") ;; esac; fi
cd "$S"
echo "$(date -u +%FT%TZ) start $NAME $PAIR seed $SEED first $FIRST deals $DEALS workers $WORKERS $* (source $(git rev-parse --short HEAD), nets $PREC${RECYCLE:+, ${RECYCLE[*]}})" >> "$W/runs.log"
"$PY" scripts/x8_match.py --source "$W/capsule/recovery" --bots configs/loop-bots.json --pair "$PAIR" --deals "$DEALS" --first "$FIRST" \
  --seed "$SEED" --workers "$WORKERS" --out "$W/runs/$NAME" "${RECYCLE[@]}" "$@" >> "$W/runs/$NAME.log" 2>&1 && rc=0 || rc=$?
echo "$(date -u +%FT%TZ) end $NAME: exit $rc" >> "$W/runs.log"
exit $rc
