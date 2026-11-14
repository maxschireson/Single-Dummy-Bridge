# boxctl: timeout=120
# boxctl: timeout=120
# loop session (Max, 05:24 UTC on 14 November: "2 boxes of each, and one box for testing"): a unit of its own (loop-switch, in
# place of the earlier one) waits for this box's BEN session to end (runs.log: "jobs-azure1-ben.txt (has ended"), stops whatever was queued
# behind it (it has moved to azure3 or been dropped), moves the source to 69b94df and starts the box on not played)|Gen 8 self-play
# (jobs-azure1.txt). It changes the source only while nothing runs from it. Returns at once.
set -euo pipefail
W=$HOME/work/loop
cat > "$W/switch.sh" <<'EOS'
#!/usr/bin/env bash
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113; MAIN=loop-collect; BOX=azure1; COMMIT=69b94dfc5295b9e803448bf0a276237a401896ae
while ! grep -Eq "jobs-azure1-ben.txt (has ended" "$W/runs.log"; do sleep 30; done
sleep 15
sudo systemctl stop loop-next loop-rungs loop-rungs2 loop-rungs3 2>/dev/null
sudo systemctl stop $MAIN loop-collect-b 2>/dev/null
pkill -u "$USER" -f scripts/x8_match.py 2>/dev/null; sleep 5
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" checkout -q $COMMIT
echo "$(date -u +%FT%TZ) azure1's role from here (Max, 05:24 UTC): not played)|Gen 8 self-play (jobs-$BOX.txt, source ${COMMIT:0:7}); its other queued tests are on azure3 or dropped" >> "$W/runs.log"
sudo systemctl reset-failed $MAIN loop-collect-b 2>/dev/null
sudo systemd-run --unit=$MAIN --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$S/$T/chain.sh" "$S/$T/jobs-$BOX.txt"
sudo systemd-run --unit=loop-collect-b --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$S/$T/chain.sh" "$S/$T/jobs-${BOX}b.txt"
EOS
sudo systemctl stop loop-switch 2>/dev/null || true; sudo systemctl reset-failed loop-switch 2>/dev/null || true
sudo systemd-run --unit=loop-switch --uid="$USER" --working-directory="$W" --setenv=HOME="$HOME" -- bash "$W/switch.sh"
sleep 3; echo "switch: $(systemctl is-active loop-switch || true) | next: $(systemctl is-active loop-next || true) | bensession: $(systemctl is-active loop-bensession || true)"; grep -c "COMMIT=69b94dfc5295b9e803448bf0a276237a401896ae" "$W/switch.sh"; tail -n 1 "$W/runs.log" | cut -c1-140; date -u +%FT%TZ
