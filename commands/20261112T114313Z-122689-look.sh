# boxctl: timeout=60
date -u +%T; echo "go71d $(systemctl is-active go71d); arena-gen71 $(systemctl is-active arena-gen71 2>/dev/null)"
tail -6 $HOME/work/gen71/go71d.log | cut -c1-260
echo "load $(cut -d' ' -f1-3 /proc/loadavg); memory available $(free -m | awk 'NR==2{print $7}') MB"
echo "g8 units: $(systemctl list-units --all --no-legend --plain 'g8-*' | awk '{print $1 "=" $3 "/" $4}' | tr '\n' ' ')"
echo "processes not of the Gen 7.1 setup, by CPU:"; ps -eo pcpu,etimes,args --sort=-pcpu --no-headers | grep -v "gen71\|smoke_gen7\|sdb-gen71x" | head -6 | cut -c1-150
