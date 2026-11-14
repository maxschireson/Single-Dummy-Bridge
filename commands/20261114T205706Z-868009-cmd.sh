# boxctl: timeout=480
# loop session (Max, 20:49 UTC: reallocate collection boxes to the rollout and training recipes): azure3's Gen 8 collection
# stops and a unit (loop-seatbench) plays bench/seat_variants.py --set horizon on round 3's gate records (one rollout decision
# in 8; settings: the plain draw twice, 1, 2 and 4 tricks then double dummy on the layout, 6 candidates, by IMPs), then starts
# the collection again (jobs-azure3-gen.txt) and its row publisher.
set -euo pipefail
W=$HOME/work/loop; S=$W/src; COMMIT=5ab40eede958f9d46112ad44ec381ac3caa18f64
sudo systemctl stop loop-chain loop-collect-b loop-rows 2>/dev/null || true; pkill -u "$USER" -f scripts/x8_match.py 2>/dev/null || true; sleep 3
git -C "$S" fetch -q --depth 12 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
echo "$(date -u +%FT%TZ) the collection stops for the rollout-recipe bench (seat_variants --set horizon; Max, 20:49 UTC)" >> "$W/runs.log"
sed -e 's/seat-bu3/horizon-bu3/g' -e 's/--every 8 --workers 8/--every 8 --workers 8 --set horizon/' -e 's/seat bench/rollout-recipe bench/g' "$W/seatbench.sh" > "$W/horizonbench.sh"
grep -n "seat_variants" "$W/horizonbench.sh" | cut -c1-220
sudo systemctl stop loop-seatbench 2>/dev/null || true; sudo systemctl reset-failed loop-seatbench 2>/dev/null || true
sudo systemd-run --unit=loop-seatbench --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$W/horizonbench.sh"
sleep 240; echo "bench: $(systemctl is-active loop-seatbench || true); decisions so far: $(wc -l < "$W/pub/exp/horizon-bu3.jsonl" 2>/dev/null || echo 0)"
grep -v Warning "$W/pub/exp/horizon-bu3.err" 2>/dev/null | tail -n 3 | cut -c1-200 || true; date -u +%FT%TZ
