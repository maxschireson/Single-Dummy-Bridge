# boxctl: timeout=600
# boxctl: timeout=600
# loop session (Max, 02:43 UTC: "only enough self play to see where we are"; external data first): azure1 moves from Stu's
# self-play (sp3se) to Gen 8 card play's self-play records (sg8e, g8a~g8b, fp32, one table a board); the row publisher
# moves to sg8e (rows read as 8s-32). sp3se's boards past its last block are built once (rows_cut.sh).
set -euo pipefail
COMMIT=5414b8a6791e6849f3d5c423eabf2b5e3567e7c5
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" diff --stat HEAD "$COMMIT" -- bridge_harness scripts | tail -2
git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
sudo systemctl stop loop-collect loop-collect-b loop-rows 2>/dev/null || true
echo "$(date -u +%FT%TZ) sp3se stopped: the box makes Gen 8 card play's self-play records (sg8e)" >> "$W/runs.log"
sudo systemctl reset-failed loop-collect loop-collect-b loop-rows 2>/dev/null || true
sudo systemd-run --unit=loop-collect --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-azure1.txt"
sudo systemd-run --unit=loop-rows --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 -- bash "$T/rows.sh" sg8e
sleep 30; echo "azure1: $(systemctl is-active loop-collect loop-rows loop-publish | tr '\n' ' ')"; tail -n 2 "$W/runs.log" | cut -c1-200
cd "$S"; bash "$T/rows_cut.sh" sp3se
echo "sp3se $(wc -l < "$W/runs/sp3se/results.jsonl") tables (final)"; free -m | sed -n 2p; date -u +%FT%TZ
