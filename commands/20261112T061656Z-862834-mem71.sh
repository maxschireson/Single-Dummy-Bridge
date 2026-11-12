# boxctl: timeout=60
# Read-only: memory of the Gen 7.1 collector's workers on this box, and boards done.
date -u +%H:%M:%S
free -m | awk 'NR==2{printf "memory: total %d MB, used %d MB, available %d MB\n", $2, $3, $7}'
pid=$(systemctl show -p MainPID --value arena-gen71)
echo "collector pid $pid up $(ps -o etimes= -p $pid | tr -d ' ')s"
ps -eo rss,etimes,pid,ppid,args --no-headers --sort=-rss | awk '/gen5_runtime|multiprocessing/ {printf "%6.0f MB  up %5ds  pid %s ppid %s\n", $1/1024, $2, $3, $4}' | head -12
run=$HOME/work/sdb-gen71/runs/gen71-vs70-azure2
[ -d "$run" ] || run=$(ls -d $HOME/work/*/runs/gen71-vs70-azure2 2>/dev/null | head -1)
echo "run $run: episodes $(ls $run/episodes 2>/dev/null | wc -l), receipts $(ls $run/receipts 2>/dev/null | wc -l), failures $(ls $run/failures 2>/dev/null | wc -l)"
sudo dmesg 2>/dev/null | grep -i -E "out of memory|oom-kill" | tail -2 | cut -c1-160; echo "(end)"
