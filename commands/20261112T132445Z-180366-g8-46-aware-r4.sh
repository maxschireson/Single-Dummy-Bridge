# boxctl: timeout=600
# boxctl: timeout=600
# g8 (azure6): the awareness match with the rule system r4. Auctions are bid beforehand at tables where r4 sits at one
# side or both, and both rooms of a board play the same auction with the bots' seats swapped: 8a-32-v41 (reads each
# side's calls by its declared system, with the scorer just trained here) against 8p-32-v41 (reads every auction as a
# house auction). Then the rule-bidding bot against Gen 7.1 in native auctions.
set -uo pipefail
SHA=663854708d4b27c402a215cea4b63028a0780a3a; FIRST=0; DEALS=1000
G=$HOME/work/g8; PY=$HOME/work/venv/bin/python; CAP=$HOME/work/capsule-gen7-capture/recovery; D=$G/src-book; REL=models/cardplay/gen8-system-scorer-v1-2026-11-12
for k in $(seq 60); do systemctl is-active --quiet g8-scorer || break; sleep 10; done
grep -q '^exit 0' "$G/sys/v2.log" || { echo "the scorer training did not end well"; tail -3 "$G/sys/v2.log" | cut -c1-200; exit 1; }
GOT=$(sha256sum "$G/sys/v2-scorer.npz" | cut -d' ' -f1); echo "scorer sha256 $GOT"
tail -6 "$G/sys/v2.log" | cut -c1-200
for dir in "$G/src" "$D"; do mkdir -p "$dir/$REL"; cp -f "$G/sys/v2-scorer.npz" "$dir/$REL/system_scorer_v1.npz"; done
git -C "$D" fetch -q --depth 1 origin "$SHA" && git -C "$D" checkout -q FETCH_HEAD || { echo "could not check out $SHA"; exit 1; }
cp "$G/src/bridge_harness/libbridge_dds.so" "$D/bridge_harness/" 2>/dev/null
mkdir -p "$G/books"; BOOK=$G/books/aw-r4-91-$FIRST.json.gz
cd "$D" && OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 nice -n 5 "$PY" scripts/gen8_auction_book.py --source "$CAP" --seed 91 --first "$FIRST" --deals "$DEALS" \
  --tables rules-precision~house-gen6,house-gen6~rules-precision,rules-precision~rules-precision --out "$BOOK" 2>&1 | tail -3 | cut -c1-300
[ -s "$BOOK" ] || { echo "no book"; exit 1; }
cat >> "$G/queue.txt" <<Q
@source $SHA
a1-8a-v-8p-r4 8a-32-v41~8p-32-v41 $FIRST $DEALS 91 --book $BOOK
c1-8c-v-7s 8c-32-v41~7s-32-v41 400 800 95
Q
sleep 60
echo "queue $(systemctl is-active g8-queue), position $(cat "$G/queue.pos") of $(wc -l < "$G/queue.txt")"; tail -3 "$G/queue.log" | cut -c1-170; tail -2 "$G/runs/a1-8a-v-8p-r4.log" 2>/dev/null | cut -c1-200
