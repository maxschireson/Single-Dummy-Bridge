# boxctl: timeout=90
set -euo pipefail
W="$HOME/work/rollout-experiments-20261114"
cat "$W/BEN_HANDOFF.json"
systemctl show stu-rollout-experiments stu-rollout-publish stu-rollout-guarantee-handoff -p Id -p ActiveState -p MainPID
ls "$W"/*publish*
cat "$W/publish.sh"
sed -n '1,180p' "$W/runtime/bridge_harness/players.py" | tail -80
rg -n "@app.route|health|def .*\(" "$HOME/work/ben/src/gameapi.py" | tail -45
git -C "$HOME/work/ben" status --short
free -m
