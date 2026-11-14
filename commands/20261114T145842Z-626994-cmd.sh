W=$HOME/work/loop; grep -o "\"epoch\": [0-9], \"seconds\": [0-9]*" $W/r4c/net.log 2>/dev/null | tail -1; tail -n 1 $W/r4c/timeline.log 2>/dev/null | cut -c1-150; systemctl is-active loop-r4
