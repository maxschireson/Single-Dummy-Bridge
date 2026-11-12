# boxctl: timeout=60
P=$HOME/work/p41; date -u +%H:%M:%S; cat $P/logs/w768e5.out | cut -c1-330; tail -c 300 $P/logs/w768e5.err; echo; tail -6 $P/logs/timeline.log; systemctl --user list-units --no-legend "p41-*" 2>/dev/null | cut -c1-120; systemctl list-units --no-legend "p41-*" 2>/dev/null | cut -c1-120; uptime; free -g | head -2
