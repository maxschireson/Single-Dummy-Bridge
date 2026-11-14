# boxctl: timeout=60
# boxctl: timeout=60
# loop session: azure6's row publisher takes the one-net Stu's self-play (sp3tb) besides what it published before (sp3sc).
set -euo pipefail
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113
sudo systemctl stop loop-rows 2>/dev/null || true; sudo systemctl reset-failed loop-rows 2>/dev/null || true
sudo systemd-run --unit=loop-rows --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 -- bash "$S/$T/rows.sh" sp3sc sp3tb
sleep 3; systemctl is-active loop-rows; echo "sp3tb $(wc -l < $W/runs/sp3tb/results.jsonl) tables since 06:11"; date -u +%FT%TZ
