# boxctl: timeout=100
D=$(lsblk -ndo NAME,TYPE | awk "\$2==\"disk\"{print \$1; exit}"); echo disk $D; a=$(grep " $D " /proc/diskstats); sleep 20; b=$(grep " $D " /proc/diskstats); python3 - "$a" "$b" <<EOF
import sys
a=list(map(int,sys.argv[1].split()[3:])); b=list(map(int,sys.argv[2].split()[3:]))
d=[y-x for x,y in zip(a,b)]
rd,wr=d[0],d[4]; rms,wms=d[3],d[7]; io=d[9]
print(f"20 s: reads {rd} ({rd/20:.0f}/s), writes {wr} ({wr/20:.0f}/s), write MB {d[6]*512/1e6:.1f}, avg write wait {wms/max(wr,1):.1f} ms, avg read wait {rms/max(rd,1):.1f} ms, busy {io/200:.0f}%")
EOF
journalctl -u g9-job-g9-cohort-azure4 --since "-150 min" --no-pager 2>/dev/null | grep -iE "publish|pushed|took|seconds" | tail -6 | cut -c1-200; curl -s -H Metadata:true "http://169.254.169.254/metadata/instance/compute?api-version=2021-02-01" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get(\"vmSize\"), d[\"storageProfile\"][\"osDisk\"][\"managedDisk\"].get(\"storageAccountType\"), d[\"storageProfile\"][\"osDisk\"].get(\"diskSizeGB\"))" 2>&1 | tail -1
