# boxctl: timeout=60
P=$HOME/work/p41; date -u +%T; cut -c1-330 $P/logs/w768e5.out | tail -2; tail -c 60 $P/logs/w768e5.err; echo; grep -c . $P/logs/w512e5.out; cut -c1-330 $P/logs/w512e5.out | tail -3
