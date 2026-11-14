# boxctl: timeout=2400
# loop session: round 4's cut on this box: the boards of its collection runs past their last published block, built once
# (rows_cut.sh, Nice 10, two workers) into pub/rows-cut for the publisher, then a line in cut.log that azure5's training
# waits for. From the collection's own checkout as it is; the chains are not stopped.
set -euo pipefail
W=$HOME/work/loop; S=$W/src
B=$(cat "$W/pub/.git/HEAD" 2>/dev/null | sed 's#.*rollout-loop-\(azure[0-9]\)-.*#\1#')
case "$B" in
  azure1) R="sg8e sg8s1 sg8s2 sg8s3 sg8s4 sg8s5 sg8s6 sg8s7 sg8s8 sp3se sps0e" ;;
  azure2) R="sp3t sp3sd sps0d" ;;
  azure6) R="sp3tb sp3sc sps0c" ;;
  azure3) R="sps0b sp3sb" ;;
  *) echo "not a cut box: $B"; exit 1 ;;
esac
git -C "$S" log -1 --format='source %h'; cd "$S"; bash training/rollout-loop-20261113/rows_cut.sh $R
echo "$(date -u +%FT%TZ) cut round4 done on $B" | tee -a "$W/pub/rows-cut/cut.log"
for r in $R; do [ -e "$W/runs/$r/results.jsonl" ] && echo "$r $(wc -l < "$W/runs/$r/results.jsonl") tables"; done | tr '\n' ' '; echo
ls "$W/pub/rows" | grep -vc log; free -m | sed -n 2p; date -u +%FT%TZ
