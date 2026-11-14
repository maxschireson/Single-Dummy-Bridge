# boxctl: timeout=120
set -eu
date -u +%FT%TZ
systemctl show loop-collect loop-collect-b loop-publish loop-rows --property=Id,ActiveState,SubState,MainPID,ExecStart,ControlGroup --no-pager
ps -eo pid,ppid,etimes,comm,args | rg 'x8_match|loop/.*chain|loop/.*rows|loop/.*pub|loop-collect' | head -35
git -C "$HOME/work/loop/src" rev-parse HEAD
git -C "$HOME/work/loop/src" status --short
df -h "$HOME"
free -m
ls "$HOME/work/loop/runs"
