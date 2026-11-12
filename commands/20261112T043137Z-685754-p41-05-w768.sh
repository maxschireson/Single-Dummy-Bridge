# boxctl: timeout=120
# p41: start the 768-wide run now, beside the 512-wide one (unit p41-w768). The chain then skips its own 768 run.
set -euo pipefail
P=$HOME/work/p41; S=$HOME/work/p41src
touch $P/NO768
echo "w768 start (beside 512) $(date -u +%T)" >> $P/logs/timeline.log
sudo systemd-run --unit=p41-w768 --uid="$(id -un)" --working-directory="$S" --setenv=HOME="$HOME" -- /bin/bash -c "$HOME/work/venv/bin/python scripts/train_gen7_policy.py --data $P/data/gen7_v41_train.npz --all-train --val-data $P/data/freshB.npz --kind suit --width 768 --epochs 3 --augment none --save-epochs --out $P/runs/w768 > $P/logs/w768.out 2> $P/logs/w768.err; echo \"w768 exit \$? \$(date -u +%T)\" >> $P/logs/timeline.log" 2>&1 | tail -1
