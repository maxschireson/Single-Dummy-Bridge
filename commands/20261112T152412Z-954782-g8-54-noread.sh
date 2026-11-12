# boxctl: timeout=60
# boxctl: timeout=60
# g8 (azure6): a second test of why Gen 8's edge over Gen 7.1 is larger head to head than against Gen 6: Gen 8 against
# a Gen 7.1 that does not read the play (7n-32-v41), on the first 800 deals of the head-to-head match (x2, seed 81).
# If Gen 7.1 does better without its reading, it was misreading Gen 8's cards. Goes in ahead of c1.
set -uo pipefail
G=$HOME/work/g8
n=$(wc -l < "$G/queue.txt"); last=$(tail -n 1 "$G/queue.txt")
case "$last" in c1-8c-v-7s*) ;; *) echo "the last line is not c1: $last"; exit 1;; esac
[ "$(cat "$G/queue.pos")" -lt $((n - 1)) ] || { echo "c1 has already started"; exit 1; }
{ head -n $((n - 1)) "$G/queue.txt"; echo "@source eac981ce07eb55630b10ce55420e5fae9c0b60ab"; echo "h2-8p41-v-7n41 8p-32-v41~7n-32-v41 0 800 81"; echo "$last"; } > "$G/queue.new" && mv "$G/queue.new" "$G/queue.txt"
echo "queue $(systemctl is-active g8-queue), position $(cat "$G/queue.pos") of $(wc -l < "$G/queue.txt")"; tail -n 5 "$G/queue.txt" | cut -c1-120
