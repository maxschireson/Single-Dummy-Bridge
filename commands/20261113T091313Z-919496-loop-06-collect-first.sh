# boxctl: timeout=600
# boxctl: timeout=600
# loop session: azure3 collects first (the round waits on games); the gate's baseline resumes after. Restart the chain
# with the branch's reordered job file. The gate match keeps its boards and resumes later.
set -euo pipefail
COMMIT=33cdc282a971901a17f721014335e3c67f58be46
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113
sudo systemctl stop loop-chain || true
echo "g0-stu0 paused at $(wc -l < "$W/runs/g0-stu0/results.jsonl") boards: $(tail -n 1 "$W/runs/g0-stu0.log" | cut -c1-120)"
git -C "$S" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"
git -C "$S" log -1 --format='source %h %s' | cut -c1-120
sudo systemctl reset-failed loop-chain 2>/dev/null || true
sudo systemd-run --unit=loop-chain --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 -- bash "$T/chain.sh" "$T/jobs-azure3.txt"
sleep 40; systemctl is-active loop-chain loop-publish | tr '\n' ' '; echo; tail -n 1 "$W/runs.log" | cut -c1-200; tail -n 1 "$W/runs/s0b.log" 2>/dev/null | cut -c1-160; date -u +%FT%TZ
