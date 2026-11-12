#!/bin/bash
# When the 768-wide run ends: score it against v4 and the 512-wide net, and push.
set -uo pipefail
P=$HOME/work/p41; S=$HOME/work/p41src; T=$S/training/policy-v4.1-20261112
log() { echo "$1 $(date -u +%T)" >> $P/logs/timeline.log; }
while ! grep -q "w768 done\|w768 exit\|w768 FAILED" $P/logs/timeline.log; do sleep 5; done
grep -q "w768 done\|w768 exit 0" $P/logs/timeline.log || exit 1
while ! grep -q "eval512 done" $P/logs/timeline.log; do sleep 5; done
bash $T/evalnet.sh 768
bash $T/push_results.sh > $P/logs/push3.log 2>&1; log "push3 done"
