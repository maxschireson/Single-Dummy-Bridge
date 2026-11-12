# boxctl: timeout=60
# Read-only: which processes hold the memory on this box.
free -m | awk 'NR==1{print "            " $0} NR==2{print}'
echo "== by kind (RSS MB, processes)"
ps -eo rss,etimes,args --no-headers | awk '
  /gameapi.py/ {k="BEN server (gameapi.py)"} 
  /gen5_runtime.py/ {k="collector and its workers"} 
  /multiprocessing/ {k="collector and its workers"} 
  /publish_gen5.py/ {k="publisher"} 
  /unittest|smoke_gen7/ {k="LEFTOVER test or preflight"} 
  {if(k==""){k="other"}; s[k]+=$1; n[k]++; k=""} 
  END {for(k in s) printf "%8.0f MB  %3d  %s\n", s[k]/1024, n[k], k}' | sort -rn
echo "== the ten largest"
ps -eo rss,etimes,pid,args --no-headers --sort=-rss | head -10 | awk '{printf "%6.0f MB  up %5ds  pid %s  %s\n", $1/1024, $2, $3, substr($0, index($0,$4), 110)}'
echo "== BEN servers, one line a lane (RSS MB, uptime s)"
for n in 1 2 3 4 5 6 7 8; do pid=$(systemctl show -p MainPID --value ben-server@$n); echo -n "lane $n: $(ps -o rss=,etimes= -p $pid 2>/dev/null | awk '{printf "%.0f MB up %ds", $1/1024, $2}'); "; done; echo
echo "== kernel: recent out-of-memory events"; sudo dmesg 2>/dev/null | grep -i -E "out of memory|oom-kill" | tail -3 | cut -c1-160; echo "(end)"
