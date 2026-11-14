# boxctl: timeout=420
# loop session (Max, 17:27 UTC: "Too much time testing relative to learning"; 17:34: "likely adopt"; 17:57: "New collections
# should flip ... We should continue collecting gen"): the BEN gate stops (stu4c is adopted; its records stay), the BEN (200)
# servers stop, the source moves to 7768d38. A unit (loop-seatbench) then plays bench/seat_variants.py on round 3's gate
# records (one rollout decision in 8, every simulated-seat setting on the same layouts; about an hour on 8 workers) and, when
# it ends, starts this box's Gen 8 self-play collection (jobs-azure3-gen.txt) and its row publisher.
set -euo pipefail
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113; COMMIT=7768d383ac104aa8f3feedcf98d582b111554906
for r in bu4c-pst200a bu4c-pst200b bu4c-pst200c; do printf '%s: %s | ' $r "$(cat "$W"/runs/$r-[1-8]/results.jsonl 2>/dev/null | wc -l)"; done; echo
sudo systemctl stop loop-bensession 2>/dev/null || true
for u in $(systemctl list-units --plain --no-legend 'loop-ben-*' | awk '{print $1}'); do sudo systemctl stop "$u"; done
pkill -u "$USER" -f scripts/x8_match.py 2>/dev/null || true; sleep 3
for n in 1 2 3 4 5 6 7 8; do sudo systemctl stop "loop-ben200@$n" 2>/dev/null || true; done
sudo systemctl stop loop-chain loop-collect-b loop-rows 2>/dev/null || true
echo "$(date -u +%FT%TZ) the BEN gate stops at $(cat "$W"/runs/bu4c-pst200[a-e]-[1-8]/results.jsonl 2>/dev/null | wc -l) deals of stu4c (adopted; Max, 17:27 and 17:57 UTC); the seat bench, then Gen 8's self-play" >> "$W/runs.log"
git -C "$S" checkout -q -- $T/jobs-azure3-ben8.txt
git -C "$S" status --short | head -5
git -C "$S" fetch -q --depth 12 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
cat > "$W/seatbench.sh" <<'EOS'
#!/usr/bin/env bash
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113; PY=$W/venv/bin/python
cd "$S"; export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
mkdir -p "$W/pub/exp"; rm -f "$W/pub/exp/seat-bu3.jsonl"
echo "$(date -u +%FT%TZ) seat bench begins (bench/seat_variants.py on round 3's gate records, one decision in 8)" >> "$W/runs.log"
# shellcheck disable=SC2046
timeout 7200 "$PY" $T/bench/seat_variants.py $(ls -d "$W"/runs/bu3-pst200[a-e]-[1-8]) --source "$W/capsule/recovery" --boards 100 --every 8 --workers 8 \
  --out "$W/pub/exp/seat-bu3.jsonl" > "$W/pub/exp/seat-bu3.txt" 2> "$W/pub/exp/seat-bu3.err"
echo "$(date -u +%FT%TZ) seat bench ended: exit $?; $(wc -l < "$W/pub/exp/seat-bu3.jsonl") decisions" >> "$W/runs.log"
sudo systemctl reset-failed loop-chain loop-rows 2>/dev/null
sudo systemd-run --unit=loop-chain --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$S/$T/chain.sh" "$S/$T/jobs-azure3-gen.txt"
# shellcheck disable=SC2046
sudo systemd-run --unit=loop-rows --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 -- bash "$S/$T/rows.sh" $(grep -v '^#' "$S/$T/jobs-azure3-gen.txt" | awk '{print $1}' | tr '\n' ' ')
EOS
sudo systemctl stop loop-seatbench 2>/dev/null || true; sudo systemctl reset-failed loop-seatbench 2>/dev/null || true
sudo systemd-run --unit=loop-seatbench --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$W/seatbench.sh"
sleep 240; systemctl is-active loop-seatbench | tr '\n' ' '; echo "decisions so far: $(wc -l < "$W/pub/exp/seat-bu3.jsonl" 2>/dev/null || echo 0)"; grep -v Warning "$W/pub/exp/seat-bu3.err" 2>/dev/null | tail -n 4 | cut -c1-200; free -g | sed -n 2p; uptime | cut -c1-75; date -u +%FT%TZ
