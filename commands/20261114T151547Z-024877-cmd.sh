W=$HOME/work/loop; grep -o "\"epoch\": [0-9], \"seconds\": [0-9]*" $W/r4c/net.log 2>/dev/null | tail -1; tail -n 3 $W/r4go.log | cut -c1-160; systemctl is-active loop-r4; date -u +%T
