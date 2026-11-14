# boxctl: timeout=300
# boxctl: timeout=300
# loop session: the waiting unit loop-rungs2 on azure3 is replaced by one on ca4c1ef, where the style calibration keeps its tables
# (--episodes). If the old unit had already begun its job file, that is said below (its boards are kept and resumed).
set -euo pipefail
W=$HOME/work/loop; S=$W/src
echo "before: loop-rungs $(systemctl is-active loop-rungs || true), loop-rungs2 $(systemctl is-active loop-rungs2 || true)"; tail -n 2 "$W/runs.log" | cut -c1-150
sudo systemctl stop loop-rungs2 2>/dev/null || true; sudo systemctl reset-failed loop-rungs2 2>/dev/null || true
cat > "$W/after-next-c.sh" <<EOS
#!/usr/bin/env bash
while [ "\$(systemctl is-active loop-rungs)" = active ]; do sleep 30; done; sleep 45
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" checkout -q ca4c1ef3529645d1bce0e2dd0f4ad95fe6c172d2
bash "$S/training/rollout-loop-20261113/rungs.sh" jobs-azure3-v41-styles.txt azure3
EOS
sudo systemd-run --unit=loop-rungs2 --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$W/after-next-c.sh"
sleep 5; echo "after: loop-rungs $(systemctl is-active loop-rungs || true); loop-rungs2 $(systemctl is-active loop-rungs2 || true)"; echo "h0-p2 boards so far: $(cat "$W"/runs/h0-p2/results.jsonl 2>/dev/null | wc -l)"; date -u +%FT%TZ
