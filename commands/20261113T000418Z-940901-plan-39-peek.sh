# boxctl: timeout=100
# boxctl: timeout=60
P=$HOME/work/plan; tail -5 $P/rnet1/logs/timeline.log; tail -2 $P/rnet1/logs/fetch.log | cut -c1-200; tail -1 $P/rnet1/logs/build.log 2>/dev/null | cut -c1-200; ls $P/rnet1/eps 2>/dev/null | wc -l; du -sh $P/rnet1/eps 2>/dev/null; uptime
