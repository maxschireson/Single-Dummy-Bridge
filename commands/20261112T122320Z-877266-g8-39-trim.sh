# boxctl: timeout=60
# boxctl: timeout=60
# g8 (azure1, now Gen 7.1's by Max's word of 11:36): cut my match queue to the match that is running, so the box is
# free when it ends. Nothing is stopped or restarted.
set -uo pipefail
G=$HOME/work/g8
pos=$(cat "$G/queue.pos"); cp "$G/queue.txt" "$G/queue.bak.$(date -u +%H%M%S)"
total=$(wc -l < "$G/queue.txt")
head -n $((pos + 1)) "$G/queue.txt" > "$G/queue.new" && mv "$G/queue.new" "$G/queue.txt"
echo "queue was $total lines at position $pos; now $(wc -l < "$G/queue.txt") lines; unit $(systemctl is-active g8-queue)"
tail -n 2 "$G/queue.txt" | cut -c1-120
n=$(ls -d "$G"/runs/g3-8x41-v-6* 2>/dev/null | head -1); [ -n "$n" ] && wc -l "$n/results.jsonl" 2>/dev/null | cut -c1-80
tail -n 2 "$G/queue.log" 2>/dev/null | cut -c1-160
