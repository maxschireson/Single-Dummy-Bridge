# boxctl: timeout=120
# boxctl: timeout=120
# g8: short matches with full records against each known opponent type, to measure how well the policy net reads that
# type's cards (scripts/gen8_play_info.py). 96 boards each.
set -uo pipefail
G=$HOME/work/g8
cat >> "$G/queue.txt" <<'Q'
k-7s 8s-32~7s-32 0 96 71 --episodes
k-6 8s-32~6-32 0 96 71 --episodes
k-5rz 8s-32~5RZ32 0 96 71 --episodes
k-1 8s-32~1 0 96 71 --episodes
k-thigh 8s-32~t-high 0 96 71 --episodes
k-tlow 8s-32~t-low 0 96 71 --episodes
k-trandom 8s-32~t-random 0 96 71 --episodes
Q
sleep 50; tail -2 "$G/queue.log" | cut -c1-160; tail -1 "$G"/runs/k-7s.log 2>/dev/null | cut -c1-160; uptime | sed 's/.*load/load/'
