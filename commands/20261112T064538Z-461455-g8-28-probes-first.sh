# boxctl: timeout=120
# boxctl: timeout=120
# g8 (azure6): the leverage probes go before the 1,600-board match that had just started (it resumes after them).
set -uo pipefail
G=$HOME/work/g8; pos=$(cat "$G/queue.pos"); run=$(sed -n "$((pos + 1))p" "$G/queue.txt")
case "$run" in
  c2-8p-v41-v-v4*)
    cp "$G/queue.txt" "$G/queue.bak.$(date -u +%H%M%S)"
    { head -n "$pos" "$G/queue.txt"; sed -n "$((pos + 2)),$((pos + 5))p" "$G/queue.txt"; echo "$run"; tail -n +$((pos + 6)) "$G/queue.txt"; } > "$G/queue.new"
    mv "$G/queue.new" "$G/queue.txt"; sudo systemctl restart g8-queue; sleep 8 ;;
  *) echo "not what I expected to be running: $run" ;;
esac
echo "queue $(systemctl is-active g8-queue), position $(cat "$G/queue.pos")"; cat -n "$G/queue.txt" | tail -n +"$pos" | cut -c1-90; tail -2 "$G/queue.log" | cut -c1-150
