# boxctl: timeout=120
# p41: the 768-wide net with the schedule stretched to five epochs (unit p41-w768e5), every epoch saved, beside the 512-wide five-epoch run.
set -euo pipefail
P=$HOME/work/p41; S=$HOME/work/p41src
echo "w768e5 start $(date -u +%T)" >> $P/logs/timeline.log
sudo systemd-run --unit=p41-w768e5 --uid="$(id -un)" --working-directory="$S" --setenv=HOME="$HOME" -- /bin/bash -c "$HOME/work/venv/bin/python scripts/train_gen7_policy.py --data $P/data/gen7_v41_train.npz --all-train --val-data $P/data/freshB.npz --kind suit --width 768 --epochs 5 --augment none --save-epochs --out $P/runs/w768e5 > $P/logs/w768e5.out 2> $P/logs/w768e5.err; echo \"w768e5 exit \$? \$(date -u +%T)\" >> $P/logs/timeline.log" 2>&1 | tail -1
tail -3 $P/logs/timeline.log; systemctl is-active p41-w512e5 p41-w768e5 p41-after768 | tr '\n' ' '; echo
