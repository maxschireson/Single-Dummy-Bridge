# boxctl: timeout=60
P=$HOME/work/p41; date -u +%T; tail -2 $P/logs/timeline.log; cat $P/logs/pairsE.log 2>/dev/null | tail -2; wc -c $P/logs/neartie.log; systemctl is-active p41-neartie; grep -c . $P/logs/neartie.log; cut -c1-235 $P/logs/neartie.log | head -150
