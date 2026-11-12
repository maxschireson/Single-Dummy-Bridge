# boxctl: timeout=180
# boxctl: timeout=180
# g8 (azure4, mine until 15:00 UTC at the latest): the native match of the two bidding systems. 8c-32-v41 bids the rule
# system r4, 8a-32-v41 the house system; both read each side's calls by its declared system (the scorer trained for r4
# on azure6, fetched from its results branch and checked by hash). Then the same rule-bidding bot against Gen 7.1.
set -uo pipefail
SHA=663854708d4b27c402a215cea4b63028a0780a3a; WANT=8f2c2f58be8e75c0dbd8a22a91b01e12a5555b06d68511be26b8f0bde8758f1d
G=$HOME/work/g8; D=$G/src; REL=models/cardplay/gen8-system-scorer-v1-2026-11-12
git -C "$D" fetch -q --depth 1 origin transfer/gen8-proto-azure6-20261112 || { echo "could not fetch the results branch"; exit 1; }
mkdir -p "$D/$REL"; git -C "$D" show FETCH_HEAD:sys/v2-scorer.npz > "$D/$REL/system_scorer_v1.npz"
GOT=$(sha256sum "$D/$REL/system_scorer_v1.npz" | cut -d' ' -f1)
[ "$GOT" = "$WANT" ] || { echo "scorer hash $GOT, wanted $WANT"; exit 1; }
echo "scorer in place: ${GOT:0:16}"
cat >> "$G/queue.txt" <<Q
@source $SHA
b1-8c-v-8a 8c-32-v41~8a-32-v41 0 800 94
c1-8c-v-7s 8c-32-v41~7s-32-v41 0 400 95
Q
sleep 100
echo "queue $(systemctl is-active g8-queue), position $(cat "$G/queue.pos") of $(wc -l < "$G/queue.txt")"; tail -3 "$G/queue.log" | cut -c1-170; tail -3 "$G/runs/b1-8c-v-8a.log" 2>/dev/null | cut -c1-200
