# boxctl: timeout=60
P=$HOME/work/p41; date -u +%T; tail -4 $P/logs/timeline.log; wc -l $P/logs/eval_w768e5.log; sed -n "14,200p" $P/logs/eval_w768e5.log | cut -c1-420
