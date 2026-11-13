# boxctl: timeout=120
# boxctl: timeout=120
# loop session: when the searched-lead rung reaches 500 deals, azure3 leaves the ladder for the matches against BEN (64)
# (jobs-azure3-ben.txt, eight lanes), and returns to the ladder's job file when they end.
set -euo pipefail
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113
cat > "$W/switch-ben.sh" <<'SH'
#!/bin/bash
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113
while [ "$(wc -l < "$W/runs/l0-pl/results.jsonl")" -lt 500 ] || [ "$(wc -l < "$W/runs/l0-pr/results.jsonl")" -lt 500 ]; do sleep 20; done
sudo systemctl stop loop-chain
echo "$(date -u +%FT%TZ) the ladder is stopped for the matches against BEN" >> "$W/runs.log"
bash "$T/chain.sh" "$T/jobs-azure3-ben.txt" ben.sh
echo "$(date -u +%FT%TZ) the matches against BEN have ended; back to the ladder" >> "$W/runs.log"
sudo systemctl reset-failed loop-chain 2>/dev/null
sudo systemd-run --unit=loop-chain --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-azure3.txt"
SH
chmod +x "$W/switch-ben.sh"
sudo systemctl stop loop-switch 2>/dev/null || true; sudo systemctl reset-failed loop-switch 2>/dev/null || true
sudo systemd-run --unit=loop-switch --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$W/switch-ben.sh"
sleep 5; systemctl is-active loop-chain loop-switch loop-publish loop-ledger | tr '\n' ' '; echo
for r in l0-pr l0-pl; do echo "$r $(wc -l < "$W/runs/$r/results.jsonl")"; done; tail -n 2 "$W/runs.log" | cut -c1-140; date -u +%FT%TZ
