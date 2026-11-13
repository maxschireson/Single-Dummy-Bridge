# boxctl: timeout=60
D=nvme0n1; a=$(grep " $D " /proc/diskstats); sleep 15; b=$(grep " $D " /proc/diskstats); python3 -c "
import sys; a=list(map(int,sys.argv[1].split()[3:])); b=list(map(int,sys.argv[2].split()[3:])); d=[y-x for x,y in zip(a,b)]
print(f\"15 s: {d[4]/15:.0f} writes/s, {d[6]*512/15e6:.1f} MB/s, avg write wait {d[7]/max(d[4],1):.1f} ms, busy {d[9]/150:.0f}%\")" "$a" "$b"; R=~/work/g9/runs/g9-cohort-azure4/run; for m in 15 30 45 60; do echo -n "$m:$(find $R/receipts -mmin -$m -type f | wc -l) "; done; echo
