# boxctl: timeout=600
# boxctl: timeout=600
# loop session (Max, 09:38 UTC: "ETA for initial calibration results?"): run the ladder's first pass now. The collection's
# second shard pauses (its boards are kept; it resumes after the ten rungs), the chain restarts from the branch's job
# file: ten rungs at 200 deals against Gen 8 card play, then the collection again.
set -euo pipefail
COMMIT=db83b7ae8c0419cefc252b4c7eb2cf2d8817bda9
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113
sudo systemctl stop loop-chain || true
echo "s0b paused at $(wc -l < "$W/runs/s0b/results.jsonl") boards: $(tail -n 1 "$W/runs/s0b.log" | cut -c1-110)"
git -C "$S" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"
git -C "$S" log -1 --format='source %h %s' | cut -c1-120
rm -rf "$W/src2" "$W"/runs/pf-stu0-* "$W"/runs/pf-stu0v1*
sudo systemctl reset-failed loop-chain 2>/dev/null || true
sudo systemd-run --unit=loop-chain --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 -- bash "$T/chain.sh" "$T/jobs-azure3.txt"
sleep 50; systemctl is-active loop-chain loop-publish | tr '\n' ' '; echo; tail -n 1 "$W/runs.log" | cut -c1-200; tail -n 1 "$W/runs/l0-stu0.log" 2>/dev/null | cut -c1-160; date -u +%FT%TZ
