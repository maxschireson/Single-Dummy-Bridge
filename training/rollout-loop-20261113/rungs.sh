#!/usr/bin/env bash
# A collecting box plays a job file of ladder rungs and goes back to collecting:  rungs.sh JOBS.txt BOX
# Stops the box's two collection chains (their boards in hand are lost, every finished board kept), runs JOBS.txt through
# chain.sh on all the cores, then restarts the chains on jobs-BOX.txt and jobs-BOXb.txt. Needs sudo for the units.
set -uo pipefail
W=$HOME/work/loop; S=$W/src; HERE=$(cd "$(dirname "$0")" && pwd); JOBS=$1; BOX=$2
sudo systemctl stop loop-collect loop-collect-b 2>/dev/null
echo "$(date -u +%FT%TZ) the collection is paused for $(basename "$JOBS")" >> "$W/runs.log"
bash "$HERE/chain.sh" "$HERE/$(basename "$JOBS")"
echo "$(date -u +%FT%TZ) $(basename "$JOBS") has ended; back to the collection" >> "$W/runs.log"
sudo systemctl reset-failed loop-collect loop-collect-b 2>/dev/null
sudo systemd-run --unit=loop-collect --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$HERE/chain.sh" "$HERE/jobs-$BOX.txt"
sudo systemd-run --unit=loop-collect-b --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$HERE/chain.sh" "$HERE/jobs-${BOX}b.txt"
