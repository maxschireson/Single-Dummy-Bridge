# boxctl: timeout=60
set -eu
cat "$HOME/work/rollout-experiments-20261114/drain-status.json"
systemctl show loop-collect loop-publish loop-rows stu-rollout-drain -p Id -p ActiveState -p MainPID
