# boxctl: timeout=120
# boxctl: timeout=120
# loop session (05:20 UTC on 14 November): when azure3's queue of tests is done and its collection has restarted (on round 3's
# two-net self-play, as the queued units' source has it), a unit of its own (loop-switch) stops that collection, moves the
# source to fe01dae (Gen 8 card play's self-play records in jobs-azure3.txt) and starts the collection again. It changes the
# source only while nothing runs from it. Returns at once.
set -euo pipefail
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113
cat > "$W/switch.sh" <<'EOS'
#!/usr/bin/env bash
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113; MAIN=loop-chain; BOX=azure3; COMMIT=fe01dae3c7b76905269c0b9378560a15385076bc
busy() { for u in loop-next loop-rungs loop-rungs2 loop-rungs3 loop-bensession; do [ "$(systemctl is-active $u)" = active ] && return 0; done; return 1; }
while :; do
  if [ "$(systemctl is-active $MAIN)" = active ] && ! busy; then
    sleep 60; busy && continue                                  # settled: no queue started again in the meantime
    grep -q '^sg8' "$S/$T/jobs-$BOX.txt" && { echo "$(date -u +%FT%TZ) the collection is already on Gen 8 records" >> "$W/runs.log"; exit 0; }
    sudo systemctl stop $MAIN loop-collect-b 2>/dev/null; sleep 5
    git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" checkout -q $COMMIT
    echo "$(date -u +%FT%TZ) the collection moves to Gen 8 card play's self-play records (source ${COMMIT:0:7})" >> "$W/runs.log"
    sudo systemctl reset-failed $MAIN loop-collect-b 2>/dev/null
    sudo systemd-run --unit=$MAIN --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$S/$T/chain.sh" "$S/$T/jobs-$BOX.txt"
    sudo systemd-run --unit=loop-collect-b --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$S/$T/chain.sh" "$S/$T/jobs-${BOX}b.txt"
    exit 0
  fi
  sleep 60
done
EOS
sudo systemctl stop loop-switch 2>/dev/null || true; sudo systemctl reset-failed loop-switch 2>/dev/null || true
sudo systemd-run --unit=loop-switch --uid="$USER" --working-directory="$W" --setenv=HOME="$HOME" -- bash "$W/switch.sh"
sleep 3; echo "switch: $(systemctl is-active loop-switch || true) | loop-chain: $(systemctl is-active loop-chain || true)"; grep -c COMMIT=fe01dae3c7b76905269c0b9378560a15385076bc "$W/switch.sh"; date -u +%FT%TZ
