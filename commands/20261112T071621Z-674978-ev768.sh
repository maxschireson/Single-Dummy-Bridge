# boxctl: timeout=60
P=$HOME/work/p41; date -u +%T; tail -3 $P/logs/timeline.log; wc -l $P/logs/eval_w768e5.log; cut -c1-300 $P/logs/eval_w768e5.log | head -60; for s in 0 3 7; do tail -1 $P/runs/reading/pools-0$s.log; done; ls $P/runs/reading/*.npz 2>/dev/null | wc -l
