#!/usr/bin/env bash
# A session of matches against BEN on azure3 (the arena's BEN lanes), its collection paused:  ben_session.sh JOBS.txt
# Stops the collection chains; starts, in each lane's network namespace, a second BEN server at 127.0.0.1:8090 with
# BEN's upstream play sampling (sample_hands_play 200, min_sample_hands_play 20 and min_sample_hands_play_bad 20; every
# other setting as that lane's own BEN (64) config) as units loop-ben200@1..8; plays JOBS.txt through chain.sh with
# ben.sh; stops the BEN (200) servers (about 0.7 GB each) and restarts the collection. Needs sudo for the units.
set -uo pipefail
W=$HOME/work/loop; S=$W/src; HERE=$(cd "$(dirname "$0")" && pwd); JOBS=$1; LANES=${LANES:-8}
sudo systemctl stop loop-chain loop-collect-b 2>/dev/null
echo "$(date -u +%FT%TZ) the collection is paused for $(basename "$JOBS")" >> "$W/runs.log"
mkdir -p "$W/ben"
for n in $(seq 1 "$LANES"); do
  . "$HOME/work/lanes/$n.env"
  sed -e 's/^sample_hands_play = .*/sample_hands_play = 200/' -e 's/^min_sample_hands_play = .*/min_sample_hands_play = 20/' \
      -e 's/^min_sample_hands_play_bad = .*/min_sample_hands_play_bad = 20/' "$BEN_CONF" > "$W/ben/ben-200-$n.conf"
  [ "$n" = 1 ] && diff "$BEN_CONF" "$W/ben/ben-200-1.conf" | grep '^[<>]' >> "$W/ben/ben-200.diff"
  cp -f "$W/ben/ben-200-1.conf" "$W/ben/ben-200.conf"
  sudo systemctl stop "loop-ben200@$n" 2>/dev/null; sudo systemctl reset-failed "loop-ben200@$n" 2>/dev/null
  sudo systemd-run --unit="loop-ben200@$n" --uid="$USER" --working-directory="$HOME/work/ben" --property=NetworkNamespacePath="/run/netns/benlane-$n" \
    --setenv=HOME="$HOME" --setenv=PYTHONUNBUFFERED=1 --setenv=OPENBLAS_NUM_THREADS=1 --setenv=OMP_NUM_THREADS=1 --setenv=MKL_NUM_THREADS=1 \
    --setenv=TF_NUM_INTRAOP_THREADS=1 --setenv=TF_NUM_INTEROP_THREADS=1 --setenv=TF_CPP_MIN_LOG_LEVEL=3 --property=Restart=always --property=RestartSec=10 \
    --property=StandardOutput=append:"$W/ben/ben200-$n.log" --property=StandardError=append:"$W/ben/ben200-$n.log" -- \
    "$HOME/work/ben-venv/bin/python" src/gameapi.py --config "$W/ben/ben-200-$n.conf" --host 127.0.0.1 --port 8090 --record false
done
for i in $(seq 1 40); do           # the servers listen once their models are loaded
  up=0; for n in $(seq 1 "$LANES"); do sudo nsenter --net="/run/netns/benlane-$n" ss -ltn 2>/dev/null | grep -q ':8090 ' && up=$((up + 1)); done
  [ "$up" = "$LANES" ] && break; sleep 15
done
echo "$(date -u +%FT%TZ) BEN (200) servers listening: $up of $LANES" >> "$W/runs.log"
bash "$HERE/chain.sh" "$HERE/$(basename "$JOBS")" ben.sh
for n in $(seq 1 "$LANES"); do sudo systemctl stop "loop-ben200@$n" 2>/dev/null; done
echo "$(date -u +%FT%TZ) $(basename "$JOBS") has ended; BEN (200) servers stopped; back to the collection" >> "$W/runs.log"
sudo systemctl reset-failed loop-chain loop-collect-b 2>/dev/null
sudo systemd-run --unit=loop-chain --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$HERE/chain.sh" "$HERE/jobs-azure3.txt"
sudo systemd-run --unit=loop-collect-b --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$HERE/chain.sh" "$HERE/jobs-azure3b.txt"
