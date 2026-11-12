# boxctl: timeout=60
P=$HOME/work/p41; date -u +%T; tail -4 $P/logs/timeline.log; cut -c1-330 $P/logs/w768e5.out | tail -2 | head -1; tail -c 80 $P/logs/w768e5.err; echo; systemctl list-units --no-legend "g8-*" "p41-*" | cut -c1-90; cat $P/logs/reading-0.out 2>/dev/null | tail -3; cat $P/runs/reading/pools-00.log 2>/dev/null | tail -2; uptime
