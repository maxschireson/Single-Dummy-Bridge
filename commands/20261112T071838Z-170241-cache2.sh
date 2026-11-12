# boxctl: timeout=60
# Read-only: the shared solver cache of azure2's cohort: size, rows, boards; the disk it sits on.
R=$HOME/work/runs/gen71-vs70-fresh-azure2
date -u +%H:%M:%S; echo "boards $(ls $R/receipts | wc -l); cache files: $(du -m $R/dds-cache.sqlite* | tr '\n' ' ')"
echo "old cohort's cache: $(du -m $HOME/work/runs/gen71-vs70-azure2/dds-cache.sqlite* | tr '\n' ' ') for $(ls $HOME/work/runs/gen71-vs70-azure2/receipts | wc -l) boards"
df -h $R | tail -1; lsblk -o NAME,SIZE,ROTA,MODEL 2>/dev/null | head -6
cat /sys/block/$(lsblk -no PKNAME $(df --output=source $R | tail -1) 2>/dev/null | head -1)/queue/scheduler 2>/dev/null
grep -E "^(RemoveIPC)" /etc/systemd/logind.conf /etc/systemd/logind.conf.d/* 2>/dev/null; echo "logind RemoveIPC default: $(systemd-analyze cat-config systemd/logind.conf 2>/dev/null | grep -i removeipc | head -2 | tr '\n' ' ')"
id -u; free -m | awk 'NR==2{print "available " $7 " MB"}'
