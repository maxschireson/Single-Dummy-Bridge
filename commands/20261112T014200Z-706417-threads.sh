# boxctl: timeout=120
# How the collector's processes use the CPUs.
uptime
echo "== top processes by CPU (pid, threads, cpu%, rss MB, command)"
ps -eo pid,nlwp,pcpu,rss,etimes,args --sort=-pcpu | head -14 | awk 'NR==1{print;next}{ $4=int($4/1024); print }' | cut -c1-150
echo "== CPU busy over 10 s"; head -1 /proc/stat > /tmp/s1; sleep 10; head -1 /proc/stat > /tmp/s2
python3 - <<'PY'
a = list(map(int, open('/tmp/s1').read().split()[1:])); b = list(map(int, open('/tmp/s2').read().split()[1:]))
d = [y - x for x, y in zip(a, b)]; idle = d[3] + d[4]; total = sum(d)
print(f"busy {100 * (total - idle) / total:.0f}% of 8 CPUs (user {100*d[0]/total:.0f}%, system {100*d[2]/total:.0f}%, iowait {100*d[4]/total:.0f}%)")
PY
echo "== threads per python worker"; for p in $(pgrep -f "multiprocessing.spawn"); do echo "$p $(ls /proc/$p/task | wc -l) threads"; done | head -10
echo "boards so far: $(find ~/work/runs/g7s-vs-g6f-01/receipts -name '*.json' | wc -l)"
