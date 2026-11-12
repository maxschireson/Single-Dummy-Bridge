# boxctl: timeout=120
# boxctl: timeout=120
# g8: the 8p against 7s match has what it needs for now (about 1,600 boards, +0.43 +- 0.085); move on to the Gen 7
# leverage match. The match can be resumed later from its folder.
set -uo pipefail
G=$HOME/work/g8
[ "$(cat "$G/queue.pos")" = 0 ] || { echo "position is $(cat "$G/queue.pos"), nothing changed"; exit 0; }
echo "x1-8p-v-7s stops at: $(tail -1 "$G/runs/x1-8p-v-7s.log" | cut -c1-110)"
echo 1 > "$G/queue.pos"; sudo systemctl restart g8-queue; sleep 25
echo "position $(cat "$G/queue.pos")"; tail -1 "$G/queue.log" | cut -c1-150
