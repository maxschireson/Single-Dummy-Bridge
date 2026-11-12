# boxctl: timeout=60
# boxctl: timeout=60
# g8 (azure6): a test of one explanation for Gen 8's edge over Gen 7.1 being larger head to head than against Gen 6:
# that it reads cards Gen 7.1 chose among equals with the net. Gen 8 against Gen 7.1 with Gen 6's tie-break
# (7g-32-v41), on the first 800 deals of the head-to-head match (x2, seed 81). Goes in ahead of c1.
set -uo pipefail
G=$HOME/work/g8
n=$(wc -l < "$G/queue.txt"); last=$(tail -n 1 "$G/queue.txt")
case "$last" in c1-8c-v-7s*) ;; *) echo "the last line is not c1: $last"; exit 1;; esac
[ "$(cat "$G/queue.pos")" -lt $((n - 1)) ] || { echo "c1 has already started"; exit 1; }
{ head -n $((n - 1)) "$G/queue.txt"; echo "@source d5f1b662b21c299c413a6007865e793e146c181b"; echo "h1-8p41-v-7g41 8p-32-v41~7g-32-v41 0 800 81"; echo "$last"; } > "$G/queue.new" && mv "$G/queue.new" "$G/queue.txt"
echo "queue $(systemctl is-active g8-queue), position $(cat "$G/queue.pos") of $(wc -l < "$G/queue.txt")"; tail -n 5 "$G/queue.txt" | cut -c1-120; tail -n 2 "$G/queue.log" | cut -c1-150
