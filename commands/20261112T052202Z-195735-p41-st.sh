# boxctl: timeout=60
P=$HOME/work/p41; tail -8 $P/logs/timeline.log; echo "--- eval768"; grep -v "^$" $P/logs/eval768.log | sed -n "1,8p;/512 wide against/,/^== heads/p" | cut -c1-330 | head -40; echo "--- final_eval"; grep -v "^$" $P/logs/final_eval.log 2>/dev/null | cut -c1-330 | head -34
