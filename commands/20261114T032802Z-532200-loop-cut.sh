# boxctl: timeout=900
# boxctl: timeout=900
# loop session (read-only, 2 threads at Nice 10, second checkout): draws with a cut, and the nets told nothing about who
# plays (their unknown-player mode), by draw_regret.py on round 3's test rows and Gen 8's held-out rows.
set -euo pipefail
W=$HOME/work/loop; S2=$W/src-lc; PY=$W/venv/bin/python; T=training/rollout-loop-20261113
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q f1beea1d2432ac4b0da55b10522758a9c230e7bb
cd "$S2"; export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
M=models/cardplay; R3=$M/stu-net-r3-20261113/policy.npz; V2=$M/rollout-net-v2-20261113/policy_epoch5.npz
SPECS="R0-as-Gen8=$V2:8s-32:8s-32 R3-as-Stu=$R3:stup0:stup0 R3-as-Gen8=$R3:8s-32:8s-32 R3-unknown=$R3:: R3-unknown-facing-Stu=$R3::stup0 R0-unknown=$V2::"
echo "== round 3's test rows (pure Stu; rollout values)"; nice -n 10 "$PY" $T/draw_regret.py "$W/r3/stu_test.npz" --bot stup0 $SPECS 2>&1 | grep -v Warning | grep -E "^--|all|phase"
echo "== Gen 8 card play's held-out rows (the search's gap)"; nice -n 10 "$PY" $T/draw_regret.py "$W/r3/val.npz" --bot 8s-32 $SPECS 2>&1 | grep -v Warning | grep -E "^--|all|phase"
date -u +%FT%TZ
