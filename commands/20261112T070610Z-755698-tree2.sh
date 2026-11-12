# boxctl: timeout=200
#!/bin/bash
P=$HOME/work/p41; S=$HOME/work/p41src; PY=$HOME/work/venv/bin/python
cd $S && git fetch -q --depth 1 origin transfer/gen7-policy-v4.1-20261112 && git show FETCH_HEAD:training/policy-v4.1-20261112/tree_overrides.py > training/policy-v4.1-20261112/tree_overrides.py
cd $P/data && nice -n 19 $PY $S/training/policy-v4.1-20261112/tree_overrides.py pairsA.npz pairsB.npz pairsC.npz pairsD.npz pairsE.npz > $P/runs/neartie/tree_overrides.txt 2>&1
cat $P/runs/neartie/tree_overrides.txt | cut -c1-260
bash $P/pushnt.sh
date -u +%T; tail -3 $P/logs/timeline.log; cut -c1-330 $P/logs/w768e5.out | tail -1; tail -c 60 $P/logs/w768e5.err; systemctl is-active g8-reading-start
