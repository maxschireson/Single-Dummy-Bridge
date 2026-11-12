# boxctl: timeout=60
P=$HOME/work/p41; tail -3 $P/logs/timeline.log; ps -eo pcpu,cputimes,etimes,args --sort=-pcpu | grep "gen7_bench" | grep -v grep | head -6 | cut -c1-60; ls -la $P/runs/bench/; tail -1 $P/logs/w768.err
