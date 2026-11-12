# boxctl: timeout=60
P=$HOME/work/p41; tail -7 $P/logs/timeline.log; tail -2 $P/logs/bench.log | cut -c1-200; tail -1 $P/logs/w768.err; tail -n +2 $P/logs/w768.out | cut -c1-420; echo "--- result head"; tail -30 $P/logs/result_head.log 2>/dev/null | cut -c1-260; uptime
