# boxctl: timeout=30
date -u +%T; systemctl show next8 -p ActiveEnterTimestamp -p MainPID -p ExecStart --value | cut -c1-200; grep -c . $HOME/work/gen8/next8.log; tail -n 4 $HOME/work/gen8/next8.log | cut -c1-200; cat $HOME/work/gen8/next.env | cut -c1-200; ps -o pid,etimes,args -p $(systemctl show next8 -p MainPID --value) | cut -c1-150
