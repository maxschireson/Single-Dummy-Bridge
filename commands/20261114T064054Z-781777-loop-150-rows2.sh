# boxctl: timeout=60
# boxctl: timeout=60
# loop session: once azure2 starts the one-net Stu's self-play (sp3t), its row publisher takes it besides sp3sd. A unit of its own
# (loop-rowswait) waits for that; returns at once.
set -euo pipefail
W=$HOME/work/loop
cat > "$W/rows-wait.sh" <<'EOS'
#!/usr/bin/env bash
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113
while ! grep -q "start sp3t " "$W/runs.log"; do sleep 60; done
sleep 30
sudo systemctl stop loop-rows 2>/dev/null; sudo systemctl reset-failed loop-rows 2>/dev/null
sudo systemd-run --unit=loop-rows --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 -- bash "$S/$T/rows.sh" sp3sd sp3t
echo "$(date -u +%FT%TZ) the row publisher takes sp3t besides sp3sd" >> "$W/runs.log"
EOS
sudo systemctl reset-failed loop-rowswait 2>/dev/null || true
sudo systemd-run --unit=loop-rowswait --uid="$USER" --working-directory="$W" --setenv=HOME="$HOME" -- bash "$W/rows-wait.sh"
sleep 2; systemctl is-active loop-rowswait loop-switch loop-next | tr '\n' ' '; tail -n 1 "$W/runs.log" | cut -c1-150; date -u +%FT%TZ
