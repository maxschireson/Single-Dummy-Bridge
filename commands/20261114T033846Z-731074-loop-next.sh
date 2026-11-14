# boxctl: timeout=300
# boxctl: timeout=300
# loop session (Max, 03:21 UTC: "Go ahead"): once the match in hand (unit loop-rungs) has ended on azure6, the source moves to
# b293707 and rungs.sh plays jobs-azure6-blind.txt (the collection pauses for it and restarts after). Launched as the unit loop-rungs2,
# so this command returns at once.
set -euo pipefail
W=$HOME/work/loop; S=$W/src
cat > "$W/after-next.sh" <<EOS
#!/usr/bin/env bash
while [ "\$(systemctl is-active loop-rungs)" = active ]; do sleep 30; done; sleep 45
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" checkout -q b2937074b08f639de3a0e58ba8bd8f10502405c0
bash "$S/training/rollout-loop-20261113/rungs.sh" jobs-azure6-blind.txt azure6
EOS
sudo systemctl reset-failed loop-rungs2 2>/dev/null || true
sudo systemd-run --unit=loop-rungs2 --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$W/after-next.sh"
sleep 5; echo "loop-rungs: $(systemctl is-active loop-rungs || true); loop-rungs2: $(systemctl is-active loop-rungs2 || true)"; tail -n 1 "$W/runs.log" | cut -c1-150; echo "h3-pt boards so far: $(cat "$W"/runs/h3-pt*/results.jsonl 2>/dev/null | wc -l)"; date -u +%FT%TZ
