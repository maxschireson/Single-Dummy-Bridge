# boxctl: timeout=60
P=$HOME/work/p41; tail -4 $P/logs/timeline.log; grep -v "^$" $P/logs/eval_w512e5.log 2>/dev/null | cut -c1-330 | head -60
