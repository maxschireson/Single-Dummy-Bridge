sudo systemctl stop loop-serve 2>/dev/null; systemctl is-active loop-serve; grep -v Warning $HOME/work/loop/exp-width/w1536.log | tail -n 1 | cut -c1-100
