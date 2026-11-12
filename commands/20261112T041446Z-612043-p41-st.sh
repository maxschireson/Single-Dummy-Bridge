# boxctl: timeout=60
P=$HOME/work/p41; cat $P/logs/timeline.log; echo "--- buildA"; tail -2 $P/logs/buildA.log 2>/dev/null | cut -c1-200; for f in w512 w768; do [ -e $P/logs/$f.err ] && { echo "--- $f"; grep -v "^$" $P/logs/$f.err | tail -3 | cut -c1-200; cat $P/logs/$f.out 2>/dev/null | cut -c1-900; }; done
echo "--- top"; ps -eo pcpu,rss,etimes,args --sort=-pcpu | awk 'NR>1 && $1>20 {printf "%s%% %.1fGB %ss %s %s %s %s %s\n", $1, $2/1048576, $3, $4, $5, $6, $7, $8}' | cut -c1-150 | head -6
echo "--- load $(cut -d' ' -f1-3 /proc/loadavg), mem avail $(awk '/MemAvailable/{printf "%.1f GB", $2/1048576}' /proc/meminfo), disk $(df -h ~ | awk 'END{print $4}') free, $(date -u +%T) UTC"
