# boxctl: timeout=90
set -eu
systemctl show loop-collect loop-collect-b loop-publish loop-rows -p Id -p ActiveState -p MainPID
ps -eo pid,ppid,etime,args | grep -E '[x]8_match.py|[c]hain.sh' | head -15
git -C "$HOME/work/loop/src" rev-parse HEAD
git -C "$HOME/work/loop/src" status --short
cat "$HOME/work/loop/RECYCLE" || true
free -m
df -h "$HOME/work"
test ! -f "$HOME/work/loop/BF16" || cat "$HOME/work/loop/BF16"
ls "$HOME/work/loop/src/models/cardplay/stu-net-r4c-20261113"
