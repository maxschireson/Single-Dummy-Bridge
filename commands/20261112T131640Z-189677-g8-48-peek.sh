# boxctl: timeout=30
# boxctl: timeout=30
# g8: where is the scorer training?
G=$HOME/work/g8; tail -n 4 "$G/sys/v2.log" | cut -c1-200; systemctl is-active g8-scorer g8-queue | tr '\n' ' '; echo "queue $(cat "$G/queue.pos") of $(wc -l < "$G/queue.txt")"; date -u +%H:%M:%S
