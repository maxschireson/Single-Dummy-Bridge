# boxctl: timeout=900
# boxctl: timeout=900
# loop session (read-only, 2 threads at Nice 10, second checkout; exp_strong.sh keeps running from the first): what a
# simulated seat gives up when it draws its card from each net, on round 3's test rows and on Gen 8's held-out rows.
set -euo pipefail
W=$HOME/work/loop; S2=$W/src-lc; PY=$W/venv/bin/python; T=training/rollout-loop-20261113
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q 4e9ee6010d25f3709e6962f5c953b0a1cc9d433a
for d in bridge_harness/libbridge_dds.so models/cardplay; do [ -e "$S2/$d" ] && [ ! -L "$S2/$d" ] && rm -rf "$S2/$d"; ln -sfn "$W/src/$d" "$S2/$d"; done
cd "$S2"; export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
M=models/cardplay
SPECS="R0-as-Gen8=$M/rollout-net-v2-20261113/policy_epoch5.npz:8s-32:8s-32 R3-as-Stu=$M/stu-net-r3-20261113/policy.npz:stup0:stup0 R3-as-Gen8=$M/stu-net-r3-20261113/policy.npz:8s-32:8s-32 R2-as-Stu=$M/stu-net-r2-20261113/policy.npz:stup0:stup0 v4.1=$M/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz"
echo "== round 3's test rows (pure Stu, the net's lead; rollout values)"; nice -n 10 "$PY" $T/draw_regret.py "$W/r3/stu_test.npz" --bot stup0 $SPECS 2>&1 | grep -v Warning
echo "== Gen 8 card play's held-out rows (the search's gap, every legal card)"; nice -n 10 "$PY" $T/draw_regret.py "$W/r3/val.npz" --bot 8s-32 $SPECS 2>&1 | grep -v Warning
systemctl is-active loop-strong | tr '\n' ' '; tail -n 2 "$W/pub/exp-strong/timeline.log" | cut -c1-160; date -u +%FT%TZ
