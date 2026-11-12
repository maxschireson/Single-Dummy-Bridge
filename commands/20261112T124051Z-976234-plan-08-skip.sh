# boxctl: timeout=300
# boxctl: timeout=120
# plan session: end my own running job ceil16b early (files 500+ at 16 layouts) so that ceil64 runs next; ceil16c covers files 1000+ later.
set -uo pipefail
P=$HOME/work/plan
pgrep -af "plan_ceiling.py --episodes $P/data/fresh_g6sp --worlds 16 --skip-files 500" | head -3
pkill -f "plan_ceiling.py --episodes $P/data/fresh_g6sp --worlds 16 --skip-files 500" || echo "nothing to stop"
sleep 20
echo "position $(cat "$P/queue.pos")"; tail -4 "$P/queue.log" | cut -c1-110; pgrep -af "plan_ceiling.py" | head -2 | cut -c1-200
