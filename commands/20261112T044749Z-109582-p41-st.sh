# boxctl: timeout=60
P=$HOME/work/p41; tail -n +2 $P/logs/w512.out; tail -1 $P/logs/w512.err; echo "--- 768"; cat $P/logs/w768.out; tail -1 $P/logs/w768.err; tail -2 $P/logs/timeline.log; uptime
