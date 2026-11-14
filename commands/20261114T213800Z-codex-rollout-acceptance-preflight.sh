# boxctl: timeout=90
set -euo pipefail
W="$HOME/work/rollout-experiments-20261114"
systemctl show stu-rollout-experiments stu-rollout-publish loop-collect -p Id -p ActiveState -p MainPID
cat "$W/run.sh" "$W/publish.sh"
find "$W/runtime/models/cardplay/stu-net-r4c-20261113" -maxdepth 1 -type f -printf '%f %s\n'
date -u +%FT%TZ
