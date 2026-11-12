# boxctl: timeout=60
P=$HOME/work/p41; date -u +%T; tail -5 $P/logs/timeline.log; cat $P/logs/eval_direct.log 2>/dev/null | cut -c1-300; ls $P/runs/reading/*.npz | wc -l; cat $P/runs/reading/pools-0?.log | grep -c table; tail -1 $P/runs/reading/pools-00.log; uptime
