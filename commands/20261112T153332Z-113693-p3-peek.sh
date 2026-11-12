# boxctl: timeout=30
date -u +%T; echo "prepnext3 $(systemctl is-active prepnext3)"; grep -E "preflight|armed|DONE|FAILED|failed" $HOME/work/lanes/prepnext3.log | tail -11 | cut -c1-260; tail -2 $HOME/work/lanes/laneswitch.log | cut -c1-200
