# boxctl: timeout=300
# boxctl: timeout=300
# g8: second wave. azure1 leaves the 8s match (8s and 8p are the same within 0.05 +- 0.04 on 684 shared deals; 8p
# continues on azure4) and goes to the leverage match; then the opponent-type matches on fresh shared deals (seed 72).
set -uo pipefail
G=$HOME/work/g8; BOX=$BOXCTL_BOX
case "$BOX" in
  azure1) JOBS="@source c03498c77184eb987d294c635b52b27bcfae028d
g2-8x-v-thigh 8x-32~t-high 0 800 72
g2-7s-v-thigh 7s-32~t-high 0 800 72
g2-8p-v-thigh 8p-32~t-high 0 800 72" ;;
  azure4) JOBS="@source c03498c77184eb987d294c635b52b27bcfae028d
g2-8p-v-6 8p-32~6-32 0 800 72
g2-7s-v-6 7s-32~6-32 0 800 72" ;;
  azure6) JOBS="@source c03498c77184eb987d294c635b52b27bcfae028d
g2-8x-v-trandom 8x-32~t-random 0 600 72
g2-7s-v-trandom 7s-32~t-random 0 600 72
n1-8n-v-8p 8n-32~8p-32 0 2000 84" ;;
  *) echo "no jobs for $BOX"; exit 1 ;;
esac
echo "$JOBS" >> "$G/queue.txt"
if [ "$BOX" = azure1 ] && [ "$(cat "$G/queue.pos")" = 0 ]; then
  echo "x1-8s-v-7s stops at: $(tail -1 "$G/runs/x1-8s-v-7s.log" | cut -c1-110)"
  echo 1 > "$G/queue.pos"; sudo systemctl restart g8-queue; sleep 20
fi
cat -n "$G/queue.txt" | cut -c1-110; echo "position $(cat "$G/queue.pos")"; tail -2 "$G/queue.log" | cut -c1-150
