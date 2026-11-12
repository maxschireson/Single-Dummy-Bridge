# boxctl: timeout=300
# boxctl: timeout=300
# g8: policy net v4.1 arrived (05:16 UTC). Put its matches ahead of everything else on this box; the match that is
# running is interrupted and resumes afterwards from its folder. Same deals as the 8p against 7s match (seed 81).
#   azure1: the nets alone (v4.1 against v4), then Gen 8 against Gen 7 with v4.1 in both, then Gen 8 with v4.1 against Gen 8 with v4
#   azure4: Gen 7 with v4.1 against Gen 7 with v4
set -uo pipefail
G=$HOME/work/g8; BOX=$BOXCTL_BOX
case "$BOX" in
  azure1) NEW="@source 73aae9b1fd628913bd64dc6e7a3def8bdd71dfb8
c2-n-v41-v-v4 n-v41~n-v4 0 4000 81
x2-8p41-v-7s41 8p-32-v41~7s-32-v41 0 1600 81
c2-8p-v41-v-v4 8p-32-v41~8p-32 0 1600 81" ;;
  azure4) NEW="@source 73aae9b1fd628913bd64dc6e7a3def8bdd71dfb8
c2-7s-v41-v-v4 7s-32-v41~7s-32 0 1600 81" ;;
  *) echo "no jobs for $BOX"; exit 1 ;;
esac
pos=$(cat "$G/queue.pos")
{ head -n "$pos" "$G/queue.txt"; echo "$NEW"; tail -n +$((pos + 1)) "$G/queue.txt" | grep -v '^@source c03498c'; } > "$G/queue.new"
mv "$G/queue.new" "$G/queue.txt"
sudo systemctl restart g8-queue
sleep 40
cat -n "$G/queue.txt" | cut -c1-110; echo "position $(cat "$G/queue.pos")"; tail -3 "$G/queue.log" | cut -c1-150
