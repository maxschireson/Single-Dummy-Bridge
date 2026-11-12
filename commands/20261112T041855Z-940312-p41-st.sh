# boxctl: timeout=60
P=$HOME/work/p41; grep "shard" $P/logs/buildA.log | tail -2; tail -1 $P/logs/buildA.log | cut -c1-80; date -u +%T
