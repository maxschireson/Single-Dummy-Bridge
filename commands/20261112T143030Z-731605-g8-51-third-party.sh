# boxctl: timeout=60
# boxctl: timeout=60
# g8 (azure6): one more match ahead of c1, for the question p41's review raised: Gen 8's edge over Gen 7 against a
# third opponent. Gen 7.1 standard against Gen 6 fast on the 800 deals where Gen 8 (8x-32-v41) has already played
# Gen 6 (g3-8x41-v-6, seed 73), so the two results can be compared deal by deal.
set -uo pipefail
G=$HOME/work/g8
n=$(wc -l < "$G/queue.txt"); last=$(tail -n 1 "$G/queue.txt")
case "$last" in c1-8c-v-7s*) ;; *) echo "the last line is not c1: $last"; exit 1;; esac
[ "$(cat "$G/queue.pos")" -lt $((n - 1)) ] || { echo "c1 has already started"; exit 1; }
{ head -n $((n - 1)) "$G/queue.txt"; echo "g3-7s41-v-6 7s-32-v41~6-32 0 800 73"; echo "$last"; } > "$G/queue.new" && mv "$G/queue.new" "$G/queue.txt"
echo "queue $(systemctl is-active g8-queue), position $(cat "$G/queue.pos") of $(wc -l < "$G/queue.txt")"; tail -n 4 "$G/queue.txt" | cut -c1-120
