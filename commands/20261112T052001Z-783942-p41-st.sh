# boxctl: timeout=60
P=$HOME/work/p41; tail -6 $P/logs/timeline.log; tail -n 1 $P/logs/w768.out | cut -c1-420; tail -1 $P/logs/w768.err | cut -c1-200; uptime
