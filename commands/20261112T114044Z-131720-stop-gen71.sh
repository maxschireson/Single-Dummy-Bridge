# boxctl: timeout=60
# azure4 stays with g8 (in use until 13:00, then g9): stop the Gen 7.1 setup before its collector starts. The prepared run is left
# in place, unstarted.
date -u +%T
echo "go71d was $(systemctl is-active go71d)"; sudo systemctl stop go71d 2>/dev/null; sleep 3
echo "go71d $(systemctl is-active go71d); arena-gen71 $(systemctl is-active arena-gen71 2>/dev/null); arena-gen71-publish $(systemctl is-active arena-gen71-publish 2>/dev/null); leftover preflight processes: $(pgrep -fc smoke_gen7)"
pkill -f "smoke_gen7.py --run $HOME/work/runs/gen71-mix-azure4" 2>/dev/null; sleep 1; echo "after: $(pgrep -fc smoke_gen7)"
tail -4 $HOME/work/gen71/go71d.log | cut -c1-200
echo "load $(cut -d' ' -f1-3 /proc/loadavg); top processes:"; ps -eo pcpu,etimes,args --sort=-pcpu --no-headers | head -6 | cut -c1-150
