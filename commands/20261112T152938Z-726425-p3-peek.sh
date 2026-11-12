# boxctl: timeout=30
date -u +%T; echo "prepnext3 $(systemctl is-active prepnext3); lane-switch $(systemctl is-active lane-switch)"; grep -v "cohort\|SyntaxError\|File\|assert\|\^" $HOME/work/lanes/prepnext3.log | tail -11 | cut -c1-260; tail -3 $HOME/work/lanes/laneswitch.log | cut -c1-200
