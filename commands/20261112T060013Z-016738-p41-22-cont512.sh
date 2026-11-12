# boxctl: timeout=120
# p41: one more epoch for the finished 512-wide net (v4.1), starting from its epoch-3 weights with the rate restarted at 0.0005
# (unit p41-w512c1), and its scoring when it ends. The two five-epoch runs keep going beside it.
set -uo pipefail
P=$HOME/work/p41; S=$HOME/work/p41src; D=training/policy-v4.1-20261112; cd $S
git fetch -q --depth 1 origin transfer/gen7-policy-v4.1-20261112
git show FETCH_HEAD:scripts/train_gen7_policy.py > scripts/train_gen7_policy.py; git show FETCH_HEAD:$D/eval_cont.sh > $D/eval_cont.sh; chmod +x $D/eval_cont.sh
grep -c "a.init" scripts/train_gen7_policy.py
echo "w512c1 start $(date -u +%T)" >> $P/logs/timeline.log
sudo systemd-run --unit=p41-w512c1 --uid="$(id -un)" --working-directory="$S" --setenv=HOME="$HOME" -- /bin/bash -c "$HOME/work/venv/bin/python scripts/train_gen7_policy.py --data $P/data/gen7_v41_train.npz --all-train --val-data $P/data/freshB.npz --kind suit --width 512 --epochs 1 --augment none --save-epochs --init $P/runs/w512/policy_epoch3.npz --lr 5e-4 --out $P/runs/w512c1 > $P/logs/w512c1.out 2> $P/logs/w512c1.err; echo \"w512c1 exit \$? \$(date -u +%T)\" >> $P/logs/timeline.log" 2>&1 | tail -1
sudo systemd-run --unit=p41-eval-w512c1 --uid="$(id -un)" --working-directory="$P" --setenv=HOME="$HOME" -- /bin/bash $S/$D/eval_cont.sh w512c1 512 2>&1 | tail -1
ls $P/data/freshCD.npz $P/data/freshB.npz | wc -l; tail -n +3 $P/logs/w512e5.out | cut -c1-330; tail -1 $P/logs/w512e5.err; tail -n +2 $P/logs/w768e5.out | cut -c1-330; tail -1 $P/logs/w768e5.err
