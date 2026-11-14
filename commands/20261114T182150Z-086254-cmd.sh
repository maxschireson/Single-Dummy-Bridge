# boxctl: timeout=480
# loop session: the seat bench again on azure3 after its fix (42caf93). The Gen 8 collection that started when the first
# try ended is stopped for it (about an hour) and starts again when the bench ends (seatbench.sh, as before).
set -euo pipefail
W=$HOME/work/loop; S=$W/src; COMMIT=42caf9330677d86cad1be452c80ae35316f6b738
sudo systemctl stop loop-seatbench loop-chain loop-rows 2>/dev/null || true
pkill -u "$USER" -f scripts/x8_match.py 2>/dev/null || true; sleep 3
git -C "$S" fetch -q --depth 12 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
echo "$(date -u +%FT%TZ) the collection waits for the seat bench (fixed, source ${COMMIT:0:7})" >> "$W/runs.log"
sudo systemctl reset-failed loop-seatbench loop-chain loop-rows 2>/dev/null || true
sudo systemd-run --unit=loop-seatbench --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$W/seatbench.sh"
sleep 300
echo "bench: $(systemctl is-active loop-seatbench || true); decisions so far: $(wc -l < "$W/pub/exp/seat-bu3.jsonl" 2>/dev/null || echo 0)"
grep -v Warning "$W/pub/exp/seat-bu3.err" 2>/dev/null | tail -n 3 | cut -c1-200 || true
tail -n 2 "$W/runs.log" | cut -c1-150; uptime | cut -c1-75; date -u +%FT%TZ
