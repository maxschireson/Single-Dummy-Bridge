# boxctl: timeout=300
# boxctl: timeout=120
# plan session: end my own ceilT12 on azure5 (5.8 s a playout from trick 1: 2.4 hours for 400 files); it moves to azure2 overnight.
set -uo pipefail
P=$HOME/work/plan
pkill -f "plan_ceiling.py --episodes $P/data/fresh_g6sp --worlds 16 --from-trick 1 --to-trick 2" || echo "nothing to stop"
sleep 25
echo "position $(cat "$P/queue.pos")"; tail -3 "$P/queue.log" | cut -c1-110; tail -1 "$P/runs/ceilT12.log" | cut -c1-80
