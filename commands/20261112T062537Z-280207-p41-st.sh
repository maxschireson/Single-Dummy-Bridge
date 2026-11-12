# boxctl: timeout=60
P=$HOME/work/p41; tail -3 $P/logs/timeline.log; sed -n "/== its epochs 3, 4 and 5/,\$p" $P/logs/eval_w512e5.log | grep -v "^$" | grep -v "\"net\"\|\"set\"" | cut -c1-330 | head -40; cat $P/logs/push_w512e5.log 2>/dev/null | tail -3; sed -n 4p $P/logs/w768e5.out | cut -c1-330; tail -1 $P/logs/w768e5.err
