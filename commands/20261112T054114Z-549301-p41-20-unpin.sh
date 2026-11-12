# boxctl: timeout=300
# p41: the 768-wide run comes first. Stop the two background checks and give both training runs all eight cores again.
# The checks run later, on the cores the 512-wide run frees when it ends.
set -uo pipefail
P=$HOME/work/p41
sudo systemctl stop p41-inf2-v4 p41-inf2-v41 2>/dev/null; sudo systemctl reset-failed "p41-inf2-*" 2>/dev/null
for pid in $(pgrep -f "train_gen7_policy.py --data"); do sudo taskset -a -cp 0-7 $pid >/dev/null && echo "unpinned $pid"; done
echo "checks stopped, runs unpinned $(date -u +%T)" >> $P/logs/timeline.log
sleep 75; tail -2 $P/logs/w512e5.err; tail -2 $P/logs/w768e5.err; date -u +%T
