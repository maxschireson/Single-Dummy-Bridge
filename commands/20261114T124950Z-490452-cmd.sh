W=$HOME/work/loop; grep MATCH $W/human.log | tail -n 2 | cut -c1-200; tail -n 2 $W/runs.log | cut -c1-150; systemctl is-active loop-arena; pgrep -u "$USER" -fc gen7_build_dataset; date -u +%T
