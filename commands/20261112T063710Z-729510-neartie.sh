# boxctl: timeout=120
#!/bin/bash
# Near-tie selectors on the fresh fork pairs (cheap: two threads, nice 19, beside the 768-wide run).
set -uo pipefail
P=$HOME/work/p41; S=$HOME/work/p41src; PY=$HOME/work/venv/bin/python; M=$HOME/work/repo/models/cardplay
cd $S
git fetch -q --depth 1 origin transfer/gen7-policy-v4.1-20261112 && git show FETCH_HEAD:scripts/gen7_near_tie.py > scripts/gen7_near_tie.py
date -u +%T
ls -la $P/data/ | cut -c20-200
ls $P/runs/ $P/runs/result_head_final 2>/dev/null | tr '\n' ' '; echo
cat > $P/neartie.sh <<'EOS'
#!/bin/bash
set -uo pipefail
P=$HOME/work/p41; S=$HOME/work/p41src; PY=$HOME/work/venv/bin/python; M=$HOME/work/repo/models/cardplay
export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2
cd $S
for n in E; do
  [ -e $P/data/pairs$n.npz ] || $PY scripts/gen7_pairs.py --episodes $P/eps$n --set $P/data/fresh${n}_raw.npz --out $P/data/pairs$n.npz --workers 2 > $P/logs/pairs$n.log 2>&1
done
tests=(); for n in B C D E; do [ -e $P/data/pairs$n.npz ] && tests+=(--test $P/data/fresh${n}_raw.npz $P/data/pairs$n.npz); done
mkdir -p $P/runs/neartie
$PY scripts/gen7_near_tie.py --net v4.1=$P/runs/w512/policy_epoch3_T.npz --net v4=$M/gen7-policy-v4-2026-11-11/gen7_policy_v4.npz \
  --head v4.1=all=$P/runs/result_head_final/result_head.npz "${tests[@]}" --drop $P/data/gen7_v41_train.npz --out $P/runs/neartie/near_tie.json > $P/logs/neartie.log 2>&1
echo "neartie exit $? $(date -u +%T)" >> $P/logs/timeline.log
EOS
chmod +x $P/neartie.sh
sudo systemd-run --unit=p41-neartie --uid="$(id -un)" --working-directory="$S" --setenv=HOME="$HOME" --nice=19 -- /bin/bash $P/neartie.sh 2>&1 | tail -1
echo; cat $P/logs/w768e5.out | cut -c1-330
