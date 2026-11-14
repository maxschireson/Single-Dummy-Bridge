#!/usr/bin/env bash
# A session of matches against BEN (200), the box's collection paused:  ben_session.sh JOBS.txt [BOX=azure3]
# On azure3 the lanes are the arena's; on another box BEN is put there by ben_install.sh, laid out the same way.
# Stops the collection chains; starts, in each lane's network namespace, a second BEN server at 127.0.0.1:8090 with
# BEN's upstream play sampling (sample_hands_play 200, min_sample_hands_play 20 and min_sample_hands_play_bad 20; every
# other setting as that lane's own BEN (64) config) as units loop-ben200@1..8; plays JOBS.txt through chain.sh with
# ben.sh; stops the BEN (200) servers (about 0.7 GB each) and restarts the collection. Needs sudo for the units.
set -uo pipefail
W=$HOME/work/loop; S=$W/src; HERE=$(cd "$(dirname "$0")" && pwd); JOBS=$1; BOX=${2:-azure3}; LANES=${LANES:-8}
MAIN=loop-collect; [ "$BOX" = azure3 ] && MAIN=loop-chain      # azure3's first chain is the unit loop-chain (rungs.sh)
sudo systemctl stop "$MAIN" loop-collect-b 2>/dev/null
for n in $(seq 1 "$LANES"); do      # a box set up by ben_install.sh has no lanes of the arena's: the namespaces are made here
  [ -e "/run/netns/benlane-$n" ] || { sudo ip netns add "benlane-$n" && sudo ip -n "benlane-$n" link set lo up; }
done
echo "$(date -u +%FT%TZ) the collection is paused for $(basename "$JOBS")" >> "$W/runs.log"
mkdir -p "$W/ben"
CONF_SHA=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['lane_config_sha256'])" "$HERE/ben/manifest.json")
for n in $(seq 1 "$LANES"); do
  BEN_CONF=; [ -e "$HOME/work/lanes/$n.env" ] && . "$HOME/work/lanes/$n.env"
  # the lane's own config where it is azure3's BEN (64) lane config; on a box whose lanes are another round's (azure2's
  # are BEN (16)) or missing, the copy of azure3's kept here
  [ "$(sha256sum "${BEN_CONF:-/dev/null}" 2>/dev/null | cut -c1-64)" = "$CONF_SHA" ] || BEN_CONF=$HERE/ben/ben-64-lane.conf
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
sudo systemctl reset-failed "$MAIN" loop-collect-b 2>/dev/null
sudo systemd-run --unit="$MAIN" --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$HERE/chain.sh" "$HERE/jobs-$BOX.txt"
sudo systemd-run --unit=loop-collect-b --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$HERE/chain.sh" "$HERE/jobs-${BOX}b.txt"
