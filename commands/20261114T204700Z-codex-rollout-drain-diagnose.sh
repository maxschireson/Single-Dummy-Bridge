# boxctl: timeout=60
sudo journalctl -u stu-rollout-drain -n 30 --no-pager
systemctl show loop-collect stu-rollout-drain -p Id -p ActiveState -p MainPID
ps -eo pid,ppid,args | grep '[x]8_match.py' | head -12
