# boxctl: timeout=60
P=$HOME/work/p41; cat $P/logs/w512.out; tail -1 $P/logs/w512.err; tail -1 $P/logs/w768.err; tail -4 $P/logs/timeline.log; cat $P/logs/pairsA.log | tail -1 | cut -c1-300
