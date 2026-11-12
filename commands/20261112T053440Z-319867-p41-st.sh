# boxctl: timeout=60
P=$HOME/work/p41; cat $P/logs/w512e5.out | cut -c1-330; tail -1 $P/logs/w512e5.err; tail -1 $P/logs/w768e5.err; for f in $P/logs/inf_*.log; do echo "$f $(wc -c < $f)"; done; ps -eo pcpu,ni,etimes,args --sort=-pcpu | grep "gen7_check" | grep -v "grep\|bash" | wc -l
