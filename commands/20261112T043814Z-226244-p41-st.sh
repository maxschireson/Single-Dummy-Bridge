# boxctl: timeout=60
P=$HOME/work/p41; tail -6 $P/logs/timeline.log; echo "--- scoreB_old"; cut -c1-260 $P/logs/scoreB_old.log
for f in w512 w768; do [ -e $P/logs/$f.err ] && { echo "--- $f"; grep -v "^$" $P/logs/$f.err | tail -2 | cut -c1-200; cat $P/logs/$f.out 2>/dev/null | cut -c1-420; }; done
echo "--- top"; ps -eo pcpu,rss,etimes,args --sort=-pcpu | awk 'NR>1 && $1>20 {printf "%s%% %.1fGB %ss %s %s\n", $1, $2/1048576, $3, $5, $14 $15 $16}' | cut -c1-110 | head -6
echo "--- load $(cut -d' ' -f1-3 /proc/loadavg), mem avail $(awk '/MemAvailable/{printf "%.1f GB", $2/1048576}' /proc/meminfo), $(date -u +%T) UTC"
