# boxctl: timeout=60
date -u +%H:%M:%S; echo "prepnext $(systemctl is-active prepnext); lane-switch $(systemctl is-active lane-switch)"; grep -v "^lane [0-9]: cohort" $HOME/work/lanes/prepnext.log | tail -14 | cut -c1-330; tail -3 $HOME/work/lanes/laneswitch.log 2>/dev/null | cut -c1-200
