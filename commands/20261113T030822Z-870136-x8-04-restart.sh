# boxctl: timeout=900
# boxctl: timeout=900
# x8 session, azure6 (Max, 03:04-03:05 UTC): finish and restart. Stop z1/z2 (kept as partial records), update to 5c77d79 (claim
# decisions forked against 8Z without claims), and run three matches on the same deals (seed 131): z3 8z-ft1~8p-32-v41 (3 workers),
# z4 8z-ft1~7s-32-v41 (3 workers, against Gen 7.1), z5 8z-v41~8p-32-v41 (2 workers, the leverage pair with z3). Then x1 resumes.
set -euo pipefail
COMMIT=5c77d79be7fef2299e00790c0ce9026d923cabb6
W=$HOME/work/x8; S=$W/src
sudo systemctl stop x8-queue2 2>/dev/null || true
pkill -f "x8_match.py --feature-forks" || true
sleep 3
sudo systemctl reset-failed x8-queue2 2>/dev/null || true
for z in z1 z2; do echo "$(date -u +%FT%TZ) $z stopped at $(wc -l < $W/runs/$z/results.jsonl 2>/dev/null || echo 0) boards (restart with 5c77d79, Max 03:05)" >> "$W/queue.log"; done
git -C "$S" fetch -q --depth 5 origin feature/gen8x-rollout-bot-20261113 && git -C "$S" checkout -q "$COMMIT"
cat > "$W/queue3.sh" <<'Q'
#!/bin/bash
set -uo pipefail
W=$HOME/work/x8; S=$W/src; PY=$HOME/work/venv/bin/python
export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 BRIDGE_DDS_CACHE=
cd "$S"
run() {   # name pair workers
  echo "$(date -u +%FT%TZ) start $1 ($2, $3 workers) source $(git rev-parse --short HEAD)" >> "$W/queue.log"
  "$PY" scripts/x8_match.py --feature-forks --source $HOME/work/capsule-gen7-capture/recovery --bots configs/x8-bots.json \
    --pair "$2" --deals 1600 --seed 131 --workers "$3" --out "$W/runs/$1" >> "$W/runs/$1.log" 2>&1
  echo "$(date -u +%FT%TZ) end $1: exit $?" >> "$W/queue.log"
}
run z3 "8z-ft1~8p-32-v41" 3 &
run z4 "8z-ft1~7s-32-v41" 3 &
run z5 "8z-v41~8p-32-v41" 2 &
wait
run x1 "8xr0-ft1~8p-32-v41" 8
Q
chmod +x "$W/queue3.sh"
sudo systemd-run --unit=x8-queue3 --uid="$USER" --working-directory="$W" --setenv=HOME="$HOME" -- "$W/queue3.sh"
sed -i 's#^x1: 8xr0-ft1.*#z3: 8z-ft1 against 8p-32-v41; z4: 8z-ft1 against 7s-32-v41 (Gen 7.1); z5: 8z-v41 against 8p-32-v41 (paired with z3: the rollout net). Seed 131. z1, z2: the same as z3, z5 before 5c77d79 (stopped early). x1: 8xr0-ft1 (blend) against 8p-32-v41.#' "$W/publish.sh"
sudo systemctl restart x8-publish
sleep 90
systemctl is-active x8-queue3 x8-publish; tail -6 "$W/queue.log"; for z in z3 z4 z5; do tail -1 "$W/runs/$z.log"; done; uptime
