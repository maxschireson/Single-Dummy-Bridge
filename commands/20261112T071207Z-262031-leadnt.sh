# boxctl: timeout=300
#!/bin/bash
P=$HOME/work/p41; S=$HOME/work/p41src; PY=$HOME/work/venv/bin/python; M=$HOME/work/repo/models/cardplay
cd $S && git fetch -q --depth 1 origin transfer/gen7-policy-v4.1-20261112 && git show FETCH_HEAD:scripts/gen7_near_tie.py > scripts/gen7_near_tie.py
export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2
tests=(); for n in B C D E; do tests+=(--test $P/data/fresh${n}_raw.npz $P/data/pairs$n.npz); done
$PY scripts/gen7_near_tie.py --net v4.1=$P/runs/w512/policy_epoch3_T.npz --net v4=$M/gen7-policy-v4-2026-11-11/gen7_policy_v4.npz --source 1 --min-pairs 150 \
  --head v4.1=all=$P/runs/result_head_final/result_head.npz "${tests[@]}" --drop $P/data/gen7_v41_train.npz --out $P/runs/neartie/near_tie_source1.json > $P/logs/neartie_source1.log 2>&1
echo "exit $?"; bash $P/pushnt.sh
grep -A7 "opening lead, gap up to 0.1\|opening lead, gap up to 0.2\|opening lead, gap 0.2\|opening lead, gap over\|opening lead, level" $P/logs/neartie_source1.log | grep "v4.1," -A7 | cut -c1-240 | head -60
date -u +%T; tail -2 $P/logs/timeline.log
