#!/usr/bin/env bash
# A match against BEN on a box that has the arena's BEN lanes (azure3): the deals in LANES shards, one a lane, each run
# inside that lane's network namespace, where the lane's own BEN server listens at the address the bot's spec names
# (ben64: 127.0.0.1:8089).
#   ben.sh NAME PAIR SEED FIRST DEALS LANES [more scripts/x8_match.py options, e.g. --episodes]
# Lane n plays DEALS/LANES deals from FIRST + (n-1)*DEALS/LANES into ~/work/loop/runs/NAME-n, through run.sh with one
# worker and --common-only (card play only: the auction is the common bidder's, as in every match of the loop). Waits
# for every lane. It resumes like run.sh. The servers (ben-server@1..8) and namespaces (benlane-1..8) are the arena
# operator's; this script only uses them and needs sudo to enter a namespace.
set -euo pipefail
W=$HOME/work/loop; S=$W/src; HERE=$(cd "$(dirname "$0")" && pwd)
NAME=$1; PAIR=$2; SEED=$3; FIRST=$4; DEALS=$5; LANES=$6; shift 6
[ $((DEALS % LANES)) -eq 0 ] || { echo "DEALS must divide by LANES"; exit 1; }
EACH=$((DEALS / LANES))
for n in $(seq 1 "$LANES"); do
  [ "$(systemctl is-active "ben-server@$n")" = active ] || { echo "$(date -u +%FT%TZ) ben-server@$n is not running" >> "$W/runs.log"; exit 1; }
  unit=loop-ben-$NAME-$n
  sudo systemctl stop "$unit" 2>/dev/null || true; sudo systemctl reset-failed "$unit" 2>/dev/null || true
  sudo systemd-run --quiet --wait --unit="$unit" --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" \
    --property=NetworkNamespacePath="/run/netns/benlane-$n" -- \
    bash "$HERE/run.sh" "$NAME-$n" "$PAIR" "$SEED" $((FIRST + (n - 1) * EACH)) "$EACH" 1 --common-only "$@" &
done
wait
