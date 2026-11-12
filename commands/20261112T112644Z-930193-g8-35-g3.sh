# boxctl: timeout=120
# boxctl: timeout=120
# g8 (azure1): the candidate's engine with policy v4.1 against existing player types, each paired with Gen 7.1's match
# on the same deals: Gen 6 fast, Gen 5RZ and bot 1.
set -uo pipefail
G=$HOME/work/g8
printf '%s\n' "@source 5b007c3fd736265787f062d6e41a1e7821f4b657" "g3-8x41-v-6 8x-32-v41~6-32 0 800 73" "g3-7s41-v-6 7s-32-v41~6-32 0 800 73" \
  "g3-8x41-v-5rz 8x-32-v41~5RZ32 0 600 73" "g3-7s41-v-5rz 7s-32-v41~5RZ32 0 600 73" \
  "g3-8x41-v-1 8x-32-v41~1 0 400 73" "g3-7s41-v-1 7s-32-v41~1 0 400 73" >> "$G/queue.txt"
sleep 45; echo "queue $(systemctl is-active g8-queue), position $(cat "$G/queue.pos")"; tail -3 "$G/queue.log" | cut -c1-160
