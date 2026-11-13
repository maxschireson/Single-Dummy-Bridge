# boxctl: timeout=30
date -u +%T; tail -n 6 $HOME/work/lanes/laneswitch.log | cut -c1-200; for n in 1 2 3 4 5 6 7 8; do . $HOME/work/lanes/$n.env; p=$(systemctl show -p MainPID --value arena-ben@$n); printf '%s:%s(%s) ' $n "$(basename $RUN)" "$( [ "$p" != 0 ] && readlink /proc/$p/cwd | xargs basename 2>/dev/null)"; done; echo
