# boxctl: timeout=60
# Read-only: what kind of memory the largest Gen 7.1 worker holds (by mapping), to see what grows.
date -u +%H:%M:%S
pid=$(systemctl show -p MainPID --value arena-gen71)
big=$(ps -o pid= --ppid $pid --sort=-rss | head -1 | tr -d ' ')
[ -e $HOME/work/gen71/watch.pid ] && [ -d /proc/$(cat $HOME/work/gen71/watch.pid) ] && big=$(cat $HOME/work/gen71/watch.pid) || echo $big > $HOME/work/gen71/watch.pid
echo "worker $big up $(ps -o etimes= -p $big | tr -d ' ')s, rss $(ps -o rss= -p $big | awk '{printf "%d", $1/1024}') MB, threads $(ls /proc/$big/task | wc -l); box available $(awk '/^MemAvailable:/ {print int($2/1024)}' /proc/meminfo) MB; boards $(ls $HOME/work/runs/gen71-vs70-azure2/receipts | wc -l)"
sudo cat /proc/$big/smaps | awk '
  /^[0-9a-f]+-[0-9a-f]+ / {name=$6; if(name=="") name="(anonymous)"; else if(name ~ /\.so/) name="shared libraries"; else if(name ~ /sqlite/) name="solver cache file"; else if(name ~ /^\[/) name=name; else name="other files"; n[name]++}
  /^Rss:/ {rss[name]+=$2} /^Anonymous:/ {an[name]+=$2}
  /^Size:/ {if(name=="(anonymous)"){sz=$2; if(sz>=60000 && sz<=66000) arenas++; if(sz>200000) bigmaps++}}
  END {for(k in rss) printf "%8.0f MB rss  %5d maps  %s\n", rss[k]/1024, n[k], k; printf "anonymous maps of about 64 MB (malloc arenas): %d; anonymous maps over 200 MB: %d\n", arenas, bigmaps}' | sort -rn | head -9
grep -E "^(VmRSS|RssAnon|RssFile|RssShmem|VmData|Threads)" /proc/$big/status | tr '\n' ' ' | tr -s ' \t' ' '; echo
tr '\0' '\n' < /proc/$big/environ 2>/dev/null | grep -E "^(MALLOC|LD_PRELOAD|BRIDGE_|OMP|OPENBLAS|TF_)" | tr '\n' ' ' | cut -c1-400; echo
