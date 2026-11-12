# boxctl: timeout=60
# Read-only: memory of the Gen 7.1 collector's workers on this box, and boards done.
date -u +%H:%M:%S
free -m | awk 'NR==2{printf "memory: total %d MB, used %d MB, available %d MB\n", $2, $3, $7}'
pid=$(systemctl show -p MainPID --value arena-gen71)
echo "collector pid $pid up $(ps -o etimes= -p $pid | tr -d ' ')s; tree $(ps -o rss= --pid $pid --ppid $pid | awk '{s+=$1} END {printf "%d", s/1024}') MB"
ps -o rss=,etimes=,pid= --ppid $pid --sort=-rss | awk '{printf "%6.0f MB up %5ds pid %s\n", $1/1024, $2, $3}' | head -9
big=$(ps -o pid= --ppid $pid --sort=-rss | head -1 | tr -d ' ')
echo "largest worker $big: $(grep -E '^(Rss|Pss|Anonymous|Shared_Clean|Private_Dirty|Swap):' /proc/$big/smaps_rollup | awk '{printf "%s %d MB; ", $1, $2/1024}')"
echo "its threads: $(ls /proc/$big/task | wc -l)"
run=$HOME/work/runs/gen71-vs70-azure2
echo "run: episodes $(ls $run/episodes | wc -l), receipts $(ls $run/receipts | wc -l), failures $(ls $run/failures | wc -l), cache $(du -m $run/dds-cache.sqlite* 2>/dev/null | awk '{s+=$1} END {print s}') MB"
sudo dmesg 2>/dev/null | grep -i -E "out of memory|oom-kill" | tail -2 | cut -c1-160; echo "(end)"
