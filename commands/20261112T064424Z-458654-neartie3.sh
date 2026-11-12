# boxctl: timeout=150
#!/bin/bash
set -uo pipefail
P=$HOME/work/p41; S=$HOME/work/p41src
cat > $P/neartie_bots.sh <<'EOS'
#!/bin/bash
P=$HOME/work/p41; S=$HOME/work/p41src; PY=$HOME/work/venv/bin/python; M=$HOME/work/repo/models/cardplay
export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2
cd $S
tests=(); for n in B C D E; do tests+=(--test $P/data/fresh${n}_raw.npz $P/data/pairs$n.npz); done
for b in 0 2; do
  $PY scripts/gen7_near_tie.py --net v4.1=$P/runs/w512/policy_epoch3_T.npz --net v4=$M/gen7-policy-v4-2026-11-11/gen7_policy_v4.npz --bot $b --min-pairs 200 \
    --head v4.1=all=$P/runs/result_head_final/result_head.npz "${tests[@]}" --drop $P/data/gen7_v41_train.npz --out $P/runs/neartie/near_tie_bot$b.json > $P/logs/neartie_bot$b.log 2>&1
  echo "neartie bot $b exit $? $(date -u +%T)" >> $P/logs/timeline.log
done
bash $P/pushnt.sh
EOS
sudo systemctl reset-failed p41-neartie 2>/dev/null
sudo systemd-run --unit=p41-neartie-bots --uid="$(id -un)" --working-directory="$S" --setenv=HOME="$HOME" --nice=19 -- /bin/bash $P/neartie_bots.sh 2>&1 | tail -1
sleep 70
tail -4 $P/logs/timeline.log; cut -c1-330 $P/logs/w768e5.out | tail -1; tail -c 100 $P/logs/w768e5.err
