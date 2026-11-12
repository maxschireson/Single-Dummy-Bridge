#!/bin/bash
# Score a finished run (width $1) against v3.1 and v4 on the held-out sets: temperatures on B, the comparison on C.
set -uo pipefail
W=${1:-512}
P=$HOME/work/p41; S=$HOME/work/p41src; PY=$HOME/work/venv/bin/python; M=$HOME/work/repo/models/cardplay
V4=$M/gen7-policy-v4-2026-11-11/gen7_policy_v4.npz; V31=$M/gen7-policy-v3.1-2026-11-11/gen7_policy_v3.1.npz
R=$P/runs/w$W; L=$P/logs/eval$W.log
export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2
cd $S
DEALS=$($PY -c "import json; print(json.loads(open('$P/logs/buildA.log').read().strip().splitlines()[-1])['deals'])")
{
echo "== temperatures fitted on B"
for e in 1 2 3; do [ -e $R/policy_epoch$e.npz ] && $PY scripts/gen7_fit_temperature.py $R/policy_epoch$e.npz $P/data/freshB.npz 1 $R/policy_epoch${e}_T.npz; done
while ! grep -q "freshC done\|fresh C failed" $P/logs/timeline.log; do sleep 5; done
for set in C B; do
  echo "== compare on fresh $set"
  TRAIN_DEALS=v3.1:12111,v4:17207,v4.1:$DEALS $PY scripts/gen7_compare_nets.py $P/data/fresh$set.npz 1 0 v3.1=$V31 v4=$V4 v4.1=$R/policy_epoch3_T.npz
  echo "== epochs on fresh $set"
  $PY scripts/gen7_compare_nets.py $P/data/fresh$set.npz 1 0 v4=$V4 e1=$R/policy_epoch1_T.npz e2=$R/policy_epoch2_T.npz e3=$R/policy_epoch3_T.npz | head -6
done
echo "== trainer figures on fresh C, all rows and by deciding bot (0 = 6-32, 2 = 7s-32)"
$PY scripts/gen7_score_nets.py $P/data/freshC.npz v3.1=$V31 v4=$V4 v4.1=$R/policy_epoch3_T.npz
for b in 0 2; do $PY scripts/gen7_score_nets.py $P/data/freshC.npz --bot $b v4=$V4 v4.1=$R/policy_epoch3_T.npz; done
echo "== heads on fresh C"
$PY scripts/gen7_head_eval.py $P/data/freshC.npz 1 0 v4=$V4 v4.1=$R/policy_epoch3_T.npz
echo "== eval done $(date -u +%T)"
} > $L 2>&1
echo "eval$W done $(date -u +%T)" >> $P/logs/timeline.log
