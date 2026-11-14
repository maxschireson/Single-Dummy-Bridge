W=$HOME/work/loop; grep MATCH $W/human.log | tail -n +16 | cut -c1-200; grep "failed\|stage\|net [hbs]A" $W/human.log | tail -2 | cut -c1-160; tail -n 1 $W/runs.log | cut -c1-150; date -u +%T
