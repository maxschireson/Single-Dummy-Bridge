# boxctl: timeout=60
# boxctl: timeout=60
P=$HOME/work/plan; echo "pos $(cat $P/queue.pos) of $(wc -l < $P/queue.txt) lines"; tail -2 $P/queue.log | cut -c1-120; ls -la $P/runs/rbc2b* 2>/dev/null; ps aux | grep -c "[p]lan_reading_bound"; uptime
