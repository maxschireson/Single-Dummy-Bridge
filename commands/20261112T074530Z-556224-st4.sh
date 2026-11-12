# boxctl: timeout=60
P=$HOME/work/p41; date -u +%T; tail -2 $P/logs/timeline.log; ls $P/runs/reading/own-*.npz 2>/dev/null | wc -l; ls $P/runs/reading/pools-*-*.npz | wc -l; cat $P/logs/eval_direct.log | cut -c1-330
