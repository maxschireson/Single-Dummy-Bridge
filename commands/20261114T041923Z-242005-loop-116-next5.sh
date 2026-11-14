# boxctl: timeout=300
# boxctl: timeout=300
# loop session (Max, 04:17 UTC on 14 November: "let's settle the other issues first"): the waiting unit loop-rungs2 on azure5 is
# replaced by one on 1a3f3ba, where jobs-azure5-v41-styles.txt plays the style calibration first and policy v4.1 inside after it.
set -euo pipefail
W=$HOME/work/loop; S=$W/src
sudo systemctl stop loop-rungs2 2>/dev/null || true; sudo systemctl reset-failed loop-rungs2 2>/dev/null || true
cat > "$W/after-next-b.sh" <<EOS
#!/usr/bin/env bash
while [ "\$(systemctl is-active loop-rungs)" = active ]; do sleep 30; done; sleep 45
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" checkout -q 1a3f3ba1d9ca2877962fd271d4dd4e29d351bf63
bash "$S/training/rollout-loop-20261113/rungs.sh" jobs-azure5-v41-styles.txt azure5
EOS
sudo systemd-run --unit=loop-rungs2 --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$W/after-next-b.sh"
sleep 5; echo "loop-rungs: $(systemctl is-active loop-rungs || true); loop-rungs2: $(systemctl is-active loop-rungs2 || true)"; tail -n 1 "$W/runs.log" | cut -c1-170; echo "h3-pg boards so far: $(cat "$W"/runs/h3-pg/results.jsonl 2>/dev/null | wc -l)"; date -u +%FT%TZ
