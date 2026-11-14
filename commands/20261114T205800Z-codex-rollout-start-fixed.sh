# boxctl: timeout=60
set -euo pipefail
W="$HOME/work/rollout-experiments-20261114"
if ! systemctl is-active --quiet stu-rollout-experiments; then
  sudo systemd-run --unit=stu-rollout-experiments --uid="$USER" --property=RuntimeMaxSec=21600 --working-directory="$W/code" bash "$W/run.sh"
fi
cat "$W/drain-status.json"
systemctl show stu-rollout-experiments stu-rollout-publish loop-collect loop-publish loop-rows -p Id -p ActiveState -p MainPID
