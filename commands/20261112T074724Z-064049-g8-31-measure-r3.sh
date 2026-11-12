# boxctl: timeout=900
# boxctl: timeout=900
# g8: the rule bidder r3 (commit 79ad090, frozen settings) on 4,000 deals of a seed nobody has looked at (307), and on
# the two seeds of the tuning run (301 tuning, 302 unseen then) for comparison with r2. Runs beside the match queue.
set -uo pipefail
G=$HOME/work/g8; D=$G/src-tune; PY=$HOME/work/venv/bin/python; CAP=$HOME/work/capsule-gen7-capture/recovery
git -C "$D" fetch -q --depth 1 origin 79ad0902ab305fc2f664bf5cc127776ac95dfdff && git -C "$D" checkout -q FETCH_HEAD || { echo "could not check out"; exit 1; }
cd "$D"; export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
for seed in 307 302 301; do
  echo "seed $seed: $(nice -n 5 "$PY" -u scripts/tune_rule_bidder.py measure --source "$CAP" --deals 4000 --seed $seed --cache "$G/ddcache" --workers 8 \
      --settings configs/rule-systems/precision.json 2>&1 | grep '^start' | cut -c8-420)"
done
