# boxctl: timeout=30
date -u +%T; tail -n 4 $HOME/work/lanes/prepp2.log | cut -c1-200; echo "prepp2 $(systemctl is-active prepp2) lane-switch $(systemctl is-active lane-switch)"; for n in 1 2 3 4 5 6 7 8; do printf '%s:%s ' $n "$(cat $HOME/work/lanes/$n.pf8p2.rc 2>/dev/null || echo running)"; done; echo; ps -eo etimes,args | grep -c "[s]moke_gen7"
