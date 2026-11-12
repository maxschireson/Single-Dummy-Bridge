# boxctl: timeout=180
# boxctl: timeout=180
# g8: leverage probes. On every box the daily unattended upgrade is told to list services instead of restarting
# them (p41's finding on the board, 06:31 UTC: it restarted a running unit on azure5). Queue changes by box:
#   azure6  near-tie windows 0.1 / 0.2 / 0.35 with policy v4 against v0, right after the running match
#   azure1  the baseline (no window) capped at 1,000 boards, then near-tie against no window, then the gate-2 matches
#   azure4  the Gen 7 baseline capped at 1,000 boards
set -uo pipefail
G=$HOME/work/g8; BOX=$BOXCTL_BOX; SHA=3d9e1f7f5a27ba265dd7e8f0e25391c7d7727c05
pos=$(cat "$G/queue.pos"); run=$(sed -n "$((pos + 1))p" "$G/queue.txt")
cp "$G/queue.txt" "$G/queue.bak.$(date -u +%H%M%S)"
restart=no
case "$BOX" in
  azure6)
    head -n $((pos + 1)) "$G/queue.txt" > "$G/queue.new"
    printf '%s\n' "@source $SHA" "l1-8n-v4-v-v0 8n-32~8n-32-v0 0 600 83" "l1-8m-v4-v-v0 8m-32~8m-32-v0 0 600 83" \
      "l1-8w-v4-v-v0 8w-32~8w-32-v0 0 600 83" >> "$G/queue.new"
    tail -n +$((pos + 2)) "$G/queue.txt" >> "$G/queue.new"; mv "$G/queue.new" "$G/queue.txt" ;;
  azure1)
    case "$run" in c1-8p-*) keep=$pos; restart=yes ;; *) keep=$((pos + 1)) ;; esac
    head -n "$keep" "$G/queue.txt" > "$G/queue.new"
    printf '%s\n' "@source $SHA" "c1-8p-v4-v-v0 8p-32~8p-32-v0 0 1000 83" "n1-8n-v-8p 8n-32~8p-32 0 700 84" \
      "n1-8m-v-8p 8m-32~8p-32 0 700 84" "g2-8x-v-thigh 8x-32~t-high 0 800 72" "g2-7s-v-thigh 7s-32~t-high 0 800 72" \
      "g2-8p-v-thigh 8p-32~t-high 0 800 72" >> "$G/queue.new"
    mv "$G/queue.new" "$G/queue.txt" ;;
  azure4)
    sed -i 's/^c1-7s-v4-v-v0 7s-32~7s-32-v0 0 2400 83$/c1-7s-v4-v-v0 7s-32~7s-32-v0 0 1000 83/' "$G/queue.txt"
    case "$run" in c1-7s-*) restart=yes ;; esac ;;
esac
[ "$restart" = yes ] && sudo systemctl restart g8-queue
if [ -d /etc/needrestart ]; then
  sudo mkdir -p /etc/needrestart/conf.d
  echo "\$nrconf{restart} = 'l';" | sudo tee /etc/needrestart/conf.d/50-list-only.conf >/dev/null
  echo "needrestart: list only"
else echo "needrestart: not installed"; fi
sleep 5
echo "$BOX: queue $(systemctl is-active g8-queue), position $(cat "$G/queue.pos"), restarted now: $restart"
cat -n "$G/queue.txt" | tail -n +$((pos > 1 ? pos : 1)) | cut -c1-90
systemctl list-timers --all 2>/dev/null | grep apt-daily-upgrade | awk '{print "upgrade timer, last ran:", $8, $9, $10}'
echo "queue unit stops since midnight: $(sudo journalctl -u g8-queue --since today 2>/dev/null | grep -c 'Stopping')"
tail -3 "$G/queue.log" | cut -c1-150
