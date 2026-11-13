# boxctl: timeout=60
# boxctl: timeout=60
P=$HOME/work/plan; W=$P/rnet2; tail -5 $W/logs/timeline.log | cut -c1-260; tail -2 $W/logs/w768.err 2>/dev/null | cut -c1-200; grep -h '"epoch"' $W/logs/w768.out 2>/dev/null | cut -c1-330; free -g | sed -n 2p; uptime
