# boxctl: timeout=60
W="$HOME/work/rollout-experiments-20261114"
cat "$W/drain-status.json"
systemctl show loop-collect stu-rollout-experiments -p Id -p ActiveState -p MainPID
ps -eo pid,ppid,etime,comm,args | grep '[x]8_match.py' | head -10
for f in "$W"/runs/*.log; do [ ! -f "$f" ] || tail -n 8 "$f"; done
sudo journalctl -u stu-rollout-drain-retry -n 8 --no-pager
