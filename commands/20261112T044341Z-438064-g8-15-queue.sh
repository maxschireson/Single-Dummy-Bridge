# boxctl: timeout=120
# boxctl: timeout=120
# g8: the leverage match on this box uses the 8p engine (the play read at exponent 1.0 at every trick), which is at
# least as good as 8s on 684 shared deals. Only a line that has not started is changed.
set -uo pipefail
G=$HOME/work/g8
pos=$(cat "$G/queue.pos")
n=$(grep -n '^c1-8s-v4-v-v0 ' "$G/queue.txt" | cut -d: -f1)
[ -n "$n" ] && [ "$n" -gt $((pos + 1)) ] || { echo "line not found or already started (pos $pos, line ${n:-none})"; exit 1; }
sed -i "${n}s/.*/c1-8p-v4-v-v0 8p-32~8p-32-v0 0 2400 83/" "$G/queue.txt"
cat -n "$G/queue.txt" | cut -c1-120; echo "position $pos"
