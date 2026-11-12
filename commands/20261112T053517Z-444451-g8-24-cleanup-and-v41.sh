# boxctl: timeout=300
# boxctl: timeout=300
# g8: (1) remove from this box the files made with the outside bidding engine (Max, 05:28 UTC); the Gen 8 branch was
# rewritten without them, so later checkouts use the new commit. (2) More boards for the policy 4.1 matches:
#   azure6: Gen 7 with v4.1 against Gen 7 as launched, deals 1600-3199 (azure4 plays 0-1599), then Gen 8 with v4.1
#           against Gen 8 with v4; azure1 keeps Gen 8 against Gen 7 with v4.1 in both.
set -uo pipefail
G=$HOME/work/g8; BOX=$BOXCTL_BOX
for d in "$G/src" "$G/src-dry"; do
  [ -d "$d" ] && rm -rf "$d/configs/gen8-books" "$d/models/cardplay/gen8-system-scorer-proto-v1-2026-11-12" "$d/bridge_harness/epbot_bidder.py" \
         "$d/configs/systems/epbot-precision.json" "$d/configs/systems/epbot-21gf.json" "$d/scripts/gen8_auction_book.py"
done
rm -rf "$G/runs/chk-book" 2>/dev/null
pos=$(cat "$G/queue.pos")
case "$BOX" in
  azure6)
    { head -n "$pos" "$G/queue.txt"; echo "@source 3f4263763010ef1ae759f93cf998c7473337ef4d"; echo "c2-7s-v41-v-v4-azure6 7s-32-v41~7s-32 1600 1600 81"; echo "c2-8p-v41-v-v4 8p-32-v41~8p-32 0 1600 81"; tail -n +$((pos + 1)) "$G/queue.txt"; } > "$G/queue.new"
    mv "$G/queue.new" "$G/queue.txt"; sudo systemctl restart g8-queue ;;
  azure1)
    n=$(grep -n '^c2-8p-v41-v-v4 ' "$G/queue.txt" | cut -d: -f1)
    if [ -n "$n" ] && [ "$n" -gt $((pos + 1)) ]; then sed -i "${n}s/.*/# (moved to azure6: c2-8p-v41-v-v4)/" "$G/queue.txt"; fi
    n=$(grep -n '^c1-8p-v4-v-v0 ' "$G/queue.txt" | cut -d: -f1)
    [ -n "$n" ] && [ "$n" -gt $((pos + 1)) ] && sed -i "${n}i @source 3f4263763010ef1ae759f93cf998c7473337ef4d" "$G/queue.txt" ;;
  azure4)
    n=$(grep -n '^c1-7s-v4-v-v0 ' "$G/queue.txt" | cut -d: -f1)
    [ -n "$n" ] && [ "$n" -gt $((pos + 1)) ] && sed -i "${n}i @source 3f4263763010ef1ae759f93cf998c7473337ef4d" "$G/queue.txt" ;;
esac
sleep 25
cat -n "$G/queue.txt" | tail -9 | cut -c1-110; echo "position $(cat "$G/queue.pos")"; tail -2 "$G/queue.log" | cut -c1-150
find "$G/src" -iname "*epbot*" -o -iname "gen8-books" | head -3
