# boxctl: timeout=180
# boxctl: timeout=180
# g8 (azure6): two short checks that p41's review asked for, ahead of the running match (which resumes afterwards from
# its results file). On tables where both sides bid the house system the candidate's two additions should change no
# card: (f1) the system scorer, 8a-32-v41 against 8p-32-v41 with no auction book; (f2) the opponent table with 1.0 for
# this opponent, 8x-32-v41 against 8p-32-v41. Every board of both should be flat.
set -uo pipefail
G=$HOME/work/g8; SHA=663854708d4b27c402a215cea4b63028a0780a3a
pos=$(cat "$G/queue.pos"); cp "$G/queue.txt" "$G/queue.bak.$(date -u +%H%M%S)"
{ head -n "$pos" "$G/queue.txt"; echo "@source $SHA"; echo "f1-8a-v-8p-house 8a-32-v41~8p-32-v41 0 100 96"; echo "f2-8x-v-8p-v41 8x-32-v41~8p-32-v41 0 100 96"; tail -n +$((pos + 1)) "$G/queue.txt"; } > "$G/queue.new"
mv "$G/queue.new" "$G/queue.txt"; sudo systemctl restart g8-queue; sleep 45
echo "queue $(systemctl is-active g8-queue), position $(cat "$G/queue.pos") of $(wc -l < "$G/queue.txt")"; cat -n "$G/queue.txt" | tail -n 5 | cut -c1-150; tail -n 3 "$G/queue.log" | cut -c1-170
