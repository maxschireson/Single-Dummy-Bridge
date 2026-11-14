# boxctl: timeout=300
# boxctl: timeout=300
# loop session (Max, 02:26 and 02:28 UTC): the strong-data experiment on azure5, its collection paused (all 8 cores):
# exp_strong.sh in a unit of its own (Gen 8's rows of v2's set against as many rows of its mix, each trained from scratch at
# 512 and 768 wide), then the collection restarts on jobs-azure5.txt whatever happened.
set -euo pipefail
COMMIT=3dc875b3342671cfa8f1e95ea19c4d065ea7fbd1
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" diff --stat HEAD "$COMMIT" -- bridge_harness scripts | tail -2
git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
df -h "$HOME" | tail -1
sudo systemctl stop loop-collect loop-collect-b 2>/dev/null || true
echo "$(date -u +%FT%TZ) the collection is paused for exp_strong.sh" >> "$W/runs.log"
cat > "$W/exp-strong-session.sh" <<EOS
#!/usr/bin/env bash
cd "$S"; THREADS=8 bash $T/exp_strong.sh > "$W/exp-strong.out" 2>&1; echo "\$(date -u +%FT%TZ) exp_strong.sh ended (exit \$?); back to the collection" >> "$W/runs.log"
sudo systemctl reset-failed loop-collect 2>/dev/null
sudo systemd-run --unit=loop-collect --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$S/$T/chain.sh" "$S/$T/jobs-azure5.txt"
EOS
sudo systemctl reset-failed loop-strong 2>/dev/null || true
sudo systemd-run --unit=loop-strong --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$W/exp-strong-session.sh"
sleep 60; systemctl is-active loop-strong loop-collect | tr '\n' ' '; tail -n 3 "$W/pub/exp-strong/timeline.log" 2>/dev/null | cut -c1-200; date -u +%FT%TZ
