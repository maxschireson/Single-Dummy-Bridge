# boxctl: timeout=60
P=$HOME/work/p41; tail -3 $P/logs/timeline.log; sed -n "/== every fresh set/,\$p" $P/logs/eval_w512e5.log | grep -v "^$" | grep -v "decisions (\|^v3.1 to\|share of draws" | cut -c1-330 | head -50
