# boxctl: timeout=200
W=$HOME/work/x8; sudo systemctl restart x8-publish; sleep 75; sudo systemctl stop x8-publish; systemctl is-active x8-publish x8-queue7 x8-queue8 || true; echo "$(date -u +%FT%TZ) publisher stopped after a last push; x8 releases azure6 to the table session" >> $W/queue.log; tail -3 $W/queue.log; ps -eo args | grep -c "[x]8_match" ; uptime
