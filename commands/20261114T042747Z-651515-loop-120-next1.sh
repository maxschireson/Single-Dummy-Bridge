# boxctl: timeout=300
# boxctl: timeout=300
# loop session: the waiting unit loop-rungs2 on azure1 is replaced by one on 3caab93, where the style calibration keeps its tables
# (--episodes). If the old unit had already begun its job file, that is said below (its boards are kept and resumed).
set -euo pipefail
W=$HOME/work/loop; S=$W/src
echo "before: loop-rungs $(systemctl is-active loop-rungs || true), loop-rungs2 $(systemctl is-active loop-rungs2 || true)"; tail -n 2 "$W/runs.log" | cut -c1-150
sudo systemctl stop loop-rungs2 2>/dev/null || true; sudo systemctl reset-failed loop-rungs2 2>/dev/null || true
cat > "$W/after-next-d.sh" <<EOS
#!/usr/bin/env bash
while [ "\$(systemctl is-active loop-rungs)" = active ]; do sleep 30; done; sleep 45
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" checkout -q 3caab93c6d1b13a50b0b5870fc695f9e1aaae922
bash "$S/training/rollout-loop-20261113/rungs.sh" jobs-azure1-styles.txt azure1
EOS
sudo systemd-run --unit=loop-rungs2 --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$W/after-next-d.sh"
sleep 5; echo "after: loop-rungs $(systemctl is-active loop-rungs || true); loop-rungs2 $(systemctl is-active loop-rungs2 || true)"; echo "h3-p2 boards so far: $(cat "$W"/runs/h3-p2/results.jsonl 2>/dev/null | wc -l)"; date -u +%FT%TZ
