# boxctl: timeout=300
# boxctl: timeout=300
# loop session (Max, 04:22 UTC on 14 November: "let's see how one bot does against Ben"; 04:23: "the gate should be on Ben"):
# azure3 leaves the sharpened-seat control it was playing (h0-p2, stopped by hand; its finished boards are kept) and the
# queue behind it, and plays the gate: ben_session.sh jobs-azure3-ben5.txt in a unit of its own (BEN (200) servers start,
# the one-net bot and its control play, the servers stop, the collection restarts). Returns at once.
set -euo pipefail
COMMIT=3caab93c6d1b13a50b0b5870fc695f9e1aaae922
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113
sudo systemctl stop loop-rungs2 2>/dev/null || true; sudo systemctl reset-failed loop-rungs2 2>/dev/null || true
sudo systemctl stop loop-rungs 2>/dev/null || true; sudo systemctl reset-failed loop-rungs 2>/dev/null || true
sudo systemctl stop loop-chain loop-collect-b 2>/dev/null || true
pkill -u "$USER" -f scripts/x8_match.py 2>/dev/null || true; sleep 3
echo "$(date -u +%FT%TZ) h0-p2 stopped by hand at $(cat "$W/runs/h0-p2/results.jsonl" 2>/dev/null | wc -l) boards: azure3 plays the gate against BEN (jobs-azure3-ben5.txt)" >> "$W/runs.log"
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" diff --stat HEAD "$COMMIT" -- bridge_harness scripts | tail -1
git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
sha256sum "$S/models/cardplay/stu-net-r3-20261113/policy.npz" | cut -c1-16
for n in 1 2 3 4 5 6 7 8; do printf '%s ' "$(systemctl is-active ben-server@$n || true)"; done; echo
sudo systemctl reset-failed loop-bensession 2>/dev/null || true
sudo systemd-run --unit=loop-bensession --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$S/$T/ben_session.sh" jobs-azure3-ben5.txt
sleep 60; systemctl is-active loop-bensession loop-chain loop-rungs loop-rungs2 | tr '\n' ' '; tail -n 4 "$W/runs.log" | cut -c1-200; pgrep -u "$USER" -fc scripts/x8_match.py || true; date -u +%FT%TZ
