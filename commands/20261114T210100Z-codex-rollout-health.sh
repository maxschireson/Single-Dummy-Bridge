# boxctl: timeout=60
W="$HOME/work/rollout-experiments-20261114"
cat "$W/drain-status.json"
systemctl show loop-collect stu-rollout-experiments stu-rollout-publish loop-publish loop-rows -p Id -p ActiveState -p MainPID
sudo journalctl -u stu-rollout-experiments -u stu-rollout-drain -n 14 --no-pager
for f in "$W"/runs/*.log; do [ ! -f "$f" ] || tail -n 6 "$f"; done
free -m
