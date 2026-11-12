# boxctl: timeout=60
# boxctl: timeout=60
# g8: fewer near-tie probes (p41's fork-pair study on the board says a window loses and the two nets pick alike):
# one window (0.1) stays, for leverage on azure6 and for strength on azure1.
set -uo pipefail
G=$HOME/work/g8
sed -i -e 's/^l1-8m-v4-v-v0 .*/# dropped: l1-8m-v4-v-v0/' -e 's/^l1-8w-v4-v-v0 .*/# dropped: l1-8w-v4-v-v0/' -e 's/^n1-8m-v-8p .*/# dropped: n1-8m-v-8p/' "$G/queue.txt"
pos=$(cat "$G/queue.pos"); echo "$BOXCTL_BOX: queue $(systemctl is-active g8-queue), position $pos"; cat -n "$G/queue.txt" | tail -n +"$pos" | cut -c1-90; tail -2 "$G/queue.log" | cut -c1-150
