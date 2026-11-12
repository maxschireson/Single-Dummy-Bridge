# boxctl: timeout=60
P=$HOME/work/p41; tail -n 2 $P/logs/w512.out | cut -c1-1500; tail -1 $P/logs/w512.err; echo "--- 768"; tail -n 1 $P/logs/w768.out | cut -c1-420; tail -1 $P/logs/w768.err; tail -6 $P/logs/timeline.log; cat $P/logs/pairsB.log | tail -1; head -12 $P/logs/eval512.log 2>/dev/null
