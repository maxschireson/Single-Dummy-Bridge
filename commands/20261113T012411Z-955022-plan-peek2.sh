# boxctl: timeout=60
# boxctl: timeout=60
P=$HOME/work/plan; tail -5 $P/rnet2/logs/timeline.log; tail -2 $P/rnet2/logs/fetch.log | cut -c1-200; tail -1 $P/rnet2/logs/build.log 2>/dev/null | cut -c1-200; ls $P/rnet2/eps 2>/dev/null | wc -l; du -sh $P/rnet2/eps 2>/dev/null; uptime
