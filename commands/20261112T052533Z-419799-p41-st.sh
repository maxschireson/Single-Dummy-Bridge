# boxctl: timeout=60
P=$HOME/work/p41; tail -3 $P/logs/timeline.log; grep -A9 "512 wide against" $P/logs/eval768.log | grep "==\|gives up\| all \|decisions," | cut -c1-330; echo "--- heads 768"; sed -n "/^== v4.1:/,\$p" $P/logs/eval768.log | cut -c1-260; echo "--- by bot"; grep "\"bot\": \|\"net\": \"v4.1\"" $P/logs/eval768.log | cut -c1-240; tail -1 $P/logs/w512e5.err
