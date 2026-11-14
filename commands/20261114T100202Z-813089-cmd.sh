W=$HOME/work/loop; grep MATCH $W/human.log | cut -c1-200; grep "stage\|failed\|rows of\|net " $W/human.log | tail -8 | cut -c1-260; tail -n 2 $W/runs.log | cut -c1-160; date -u +%T
