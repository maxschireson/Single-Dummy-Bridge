# boxctl: timeout=60
P=$HOME/work/p41; date -u +%T; tail -3 $P/logs/timeline.log; grep -c . $P/logs/w768e5.out; cut -c1-330 $P/logs/w768e5.out | tail -3; echo; systemctl list-units --no-legend "g8-*" "p41-*" | cut -c1-70; tail -1 $P/runs/reading/pools-00.log 2>/dev/null; head -c 600 $P/logs/eval_w768e5.log 2>/dev/null
