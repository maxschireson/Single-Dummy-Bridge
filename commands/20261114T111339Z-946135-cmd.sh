# boxctl: timeout=600
# loop session (read-only, one thread, Nice 15): the experiment's nets pair by pair on the held-out SiD rows, the difference
# in tricks given up with its standard error clustered by deal (regret_pairs.py).
set -euo pipefail
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113; PY=$W/venv/bin/python; X=$W/exp-human; O=$S/models/cardplay/stu-exp-human-20261114
cd "$S"; export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
for pair in "m10 m10h" "m10 m10h4" "m10 m10F" "m10 m10A" "m10h m10h4" "bf mf" "s10 s10h"; do
  set -- $pair
  echo "== $1 -> $2"; nice -n 15 "$PY" $T/regret_pairs.py "$X/stu_eval.npz" "$O/$1.npz" "$O/$2.npz" 2>&1 | tail -n 6 | cut -c1-230
done
echo "== r3 -> m10h4"; nice -n 15 "$PY" $T/regret_pairs.py "$X/stu_eval.npz" "$W/pub/train-r3/policy.npz" "$O/m10h4.npz" 2>&1 | tail -n 6 | cut -c1-230
date -u +%T
