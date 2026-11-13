# boxctl: timeout=600
# boxctl: timeout=600
# loop session: azure3's chain on the job file at e760e5e (lead rungs' first 200 deals before round 1's rungs; the
# collection at one table a board). The run in hand resumes.
set -euo pipefail
COMMIT=e760e5e7823699c8dabcd4cc84f0386c29fc4080
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113
sudo systemctl stop loop-chain || true
echo "l0-p at $(wc -l < "$W/runs/l0-p/results.jsonl") boards"
git -C "$S" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"
git -C "$S" log -1 --format='source %h %s' | cut -c1-110
sudo systemctl reset-failed loop-chain 2>/dev/null || true
sudo systemd-run --unit=loop-chain --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-azure3.txt"
sleep 25; systemctl is-active loop-chain loop-publish | tr '\n' ' '; echo; tail -n 2 "$W/runs.log" | cut -c1-150; date -u +%FT%TZ
