# boxctl: timeout=60
P=$HOME/work/p41; date -u +%T; tail -2 $P/logs/timeline.log; cat $P/logs/eval_direct.log | cut -c1-330; cat $P/runs/reading/pools-0?.log | grep -c table; ls $P/runs/reading/pools-*-*.npz | wc -l
