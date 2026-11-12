# boxctl: timeout=300
# p41: the four background checks slowed both training runs to about half speed. Stop them, give the training runs cores 0-5 to themselves,
# and run two checks (v4 and 4.1 on the same shard of fresh tables) on cores 6 and 7 only.
set -uo pipefail
P=$HOME/work/p41; S=$HOME/work/p41src; PY=$HOME/work/venv/bin/python; M=$HOME/work/repo/models/cardplay
sudo systemctl stop p41-inf-v4-0 p41-inf-v41-0 p41-inf-v4-1 p41-inf-v41-1 2>/dev/null; sudo systemctl reset-failed "p41-inf-*" 2>/dev/null
for pid in $(pgrep -f "train_gen7_policy.py --data"); do sudo taskset -a -cp 0-5 $pid >/dev/null && echo "pinned $pid to cores 0-5"; done
ls $P/epsV/s0 | wc -l; ls $P/epsV/s1 | wc -l
SECS=$(( $(date -u -d "today 06:42:00" +%s) - $(date -u +%s) ))
for n in v4 v41; do
  pol=$M/gen7-policy-v4-2026-11-11/gen7_policy_v4.npz; [ $n = v41 ] && pol=$P/runs/w512/policy_epoch3_T.npz
  sudo systemd-run --unit=p41-inf2-$n --uid="$(id -un)" --working-directory="$S" --setenv=HOME="$HOME" --setenv=OPENBLAS_NUM_THREADS=1 --setenv=OMP_NUM_THREADS=1 --property="CPUAffinity=6 7" -- /bin/bash -c "$PY scripts/gen7_check.py inference --episodes $P/epsV/s0 --split -1 --tables 100000 --seconds $SECS --policy $pol --out $P/runs/infer/${n}_s0.json > $P/logs/inf_${n}_s0.log 2>&1; echo \"inf2 $n exit \$? \$(date -u +%T)\" >> $P/logs/timeline.log" 2>&1 | tail -1
done
sleep 45; tail -1 $P/logs/w512e5.err; tail -1 $P/logs/w768e5.err; ps -eo pcpu,psr,etimes,args --sort=-pcpu | grep "gen7_check.py inference\|train_gen7" | grep -v "grep\|bash" | awk '{print $1, "cpu" $2, $3 "s", $5, $6}' | head -6; date -u +%T
