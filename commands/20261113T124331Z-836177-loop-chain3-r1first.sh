# boxctl: timeout=600
# boxctl: timeout=600
# loop session: azure3's chain on the job file at 25d4dd0 (azure5: the collection with rolled-out leads, spr0; azure3:
# round 1's rungs as a 200-deal first pass, then the lead rungs to 500). The run in hand keeps its boards.
set -euo pipefail
COMMIT=25d4dd03d20cd60425e33669edcf9c0a5f8224a5
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113
sudo systemctl stop loop-chain || true
tail -n 2 "$W/runs.log" | cut -c1-140
for r in sp0 l0-pr l0-pl; do [ -f "$W/runs/$r/results.jsonl" ] && echo "$r $(wc -l < "$W/runs/$r/results.jsonl") boards"; done
git -C "$S" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"
git -C "$S" log -1 --format='source %h %s' | cut -c1-110
sudo systemctl reset-failed loop-chain 2>/dev/null || true
sudo systemd-run --unit=loop-chain --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-azure3.txt"
sleep 40; systemctl is-active loop-chain loop-publish | tr '\n' ' '; echo; tail -n 2 "$W/runs.log" | cut -c1-150; df -h "$W" | tail -1; date -u +%FT%TZ
