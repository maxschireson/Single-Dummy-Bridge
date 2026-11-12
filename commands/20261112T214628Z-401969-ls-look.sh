# boxctl: timeout=30
date -u +%T; systemctl show lane-switch -p ExecStart --value | grep -o "path=[^ ]*"; for f in $HOME/work/lanes/laneswitch.log $HOME/work/lanes/switch.log; do [ -e $f ] && { echo "== $f"; tail -n 12 $f | cut -c1-200; }; done; for n in 1 2 3 4 5 6 7 8; do printf '%s:%s ' $n "$(. $HOME/work/lanes/$n.env; basename $RUN)"; done; echo
