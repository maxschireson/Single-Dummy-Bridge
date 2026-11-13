# boxctl: timeout=60
df -h / | tail -1; D=nvme0n1; a=$(grep " $D " /proc/diskstats); sleep 15; b=$(grep " $D " /proc/diskstats); python3 -c "
import sys; a=list(map(int,sys.argv[1].split()[3:])); b=list(map(int,sys.argv[2].split()[3:])); d=[y-x for x,y in zip(a,b)]
print(f\"15 s: {d[4]/15:.0f} writes/s, {d[6]*512/15e6:.1f} MB/s, avg write wait {d[7]/max(d[4],1):.1f} ms, busy {d[9]/150:.0f}%\")" "$a" "$b"; ps -o pid= -p 5704 >/dev/null && echo "pid 5704 still running" || echo "pid 5704 gone"
