# boxctl: timeout=900
# boxctl: timeout=900
# loop session (read-only, 2 threads at Nice 10, second checkout): the strong-data experiment's four nets and v2, told
# they are Gen 8, by draw_regret.py on round 3's test rows and on Gen 8's held-out rows; and the experiment's own log.
set -euo pipefail
W=$HOME/work/loop; S2=$W/src-lc; PY=$W/venv/bin/python; T=training/rollout-loop-20261113
cd "$S2"; export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
grep -E "trained|held-out|v2 on|epochs" "$W/pub/exp-strong/timeline.log" | cut -c1-230
X=$W/exp-strong; M=models/cardplay
SPECS="v2-full=$M/rollout-net-v2-20261113/policy_epoch5.npz:8s-32:8s-32 STRONG-768=$X/strong-768/policy.npz:8s-32:8s-32 MIX-768=$X/mix-768/policy.npz:8s-32:8s-32 STRONG-512=$X/strong-512/policy.npz:8s-32:8s-32 MIX-512=$X/mix-512/policy.npz:8s-32:8s-32"
echo "== round 3's test rows (pure Stu; rollout values)"; nice -n 10 "$PY" $T/draw_regret.py "$W/r3/stu_test.npz" --bot stup0 $SPECS 2>&1 | grep -v Warning | grep -E "^--|all|phase"
echo "== Gen 8 card play's held-out rows (the search's gap)"; nice -n 10 "$PY" $T/draw_regret.py "$W/r3/val.npz" --bot 8s-32 $SPECS 2>&1 | grep -v Warning | grep -E "^--|all|phase"
systemctl is-active loop-rungs loop-collect | tr '\n' ' '; tail -n 2 "$W/runs.log" | cut -c1-170; date -u +%FT%TZ
