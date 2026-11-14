# boxctl: timeout=60
set -eu
W="$HOME/work/rollout-experiments-20261114"
cat "$W/drain-status.json"
systemctl show loop-collect loop-publish loop-rows stu-rollout-experiments -p Id -p ActiveState -p MainPID
sudo journalctl -u stu-rollout-drain-retry -u stu-rollout-experiments -n 20 --no-pager
for f in "$W"/runs/*.log; do [ ! -f "$f" ] || tail -n 6 "$f"; done
free -m
