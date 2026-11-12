# boxctl: timeout=600
# p41: 512 wide against 768 wide at the same epoch, on the same held-out decisions, with intervals from bootstrap draws of deals.
set -uo pipefail
P=$HOME/work/p41; S=$HOME/work/p41src; PY=$HOME/work/venv/bin/python
export OPENBLAS_NUM_THREADS=3 OMP_NUM_THREADS=3
cd $S
for set in B C; do for e in 1 2; do
  echo "== fresh $set, epoch $e"
  $PY scripts/gen7_compare_nets.py $P/data/fresh$set.npz 1 0 w512e$e=$P/runs/w512/policy_epoch$e.npz w768e$e=$P/runs/w768/policy_epoch$e.npz | sed -n '1,3p;/ all /p'
done; done
tail -1 $P/logs/w768.err; tail -3 $P/logs/timeline.log
