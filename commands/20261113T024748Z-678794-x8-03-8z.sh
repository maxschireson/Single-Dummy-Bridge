# boxctl: timeout=900
# boxctl: timeout=900
# x8 session, azure6: Max (02:39-02:41 UTC) wants pure rollouts (8Z) for leverage. Pause x1 (8xr0-ft1; it resumes later from its
# results.jsonl), update the checkout, and run 8z-ft1 and 8z-v41 side by side on the same deals (4 workers each); then resume x1.
set -euo pipefail
COMMIT=0a8f55f1fb9e4c7f0a05f173399abb558a32368c
W=$HOME/work/x8; S=$W/src
sudo systemctl stop x8-queue 2>/dev/null || true
sudo systemctl reset-failed x8-queue 2>/dev/null || true
echo "$(date -u +%FT%TZ) x1 paused at $(wc -l < $W/runs/x1/results.jsonl) boards (8Z first, Max 02:41)" >> "$W/queue.log"
git -C "$S" fetch -q --depth 5 origin feature/gen8x-rollout-bot-20261113 && git -C "$S" checkout -q "$COMMIT"
cat > "$W/queue2.sh" <<'Q'
#!/bin/bash
set -uo pipefail
W=$HOME/work/x8; S=$W/src; PY=$HOME/work/venv/bin/python
export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 BRIDGE_DDS_CACHE=
cd "$S"
run() {   # name pair workers
  echo "$(date -u +%FT%TZ) start $1 ($2) source $(git rev-parse --short HEAD)" >> "$W/queue.log"
  "$PY" scripts/x8_match.py --feature-forks --source $HOME/work/capsule-gen7-capture/recovery --bots configs/x8-bots.json \
    --pair "$2" --deals 1600 --seed 131 --workers "$3" --out "$W/runs/$1" >> "$W/runs/$1.log" 2>&1
  echo "$(date -u +%FT%TZ) end $1: exit $?" >> "$W/queue.log"
}
run z1 "8z-ft1~8p-32-v41" 4 &
run z2 "8z-v41~8p-32-v41" 4 &
wait
run x1 "8xr0-ft1~8p-32-v41" 8
Q
chmod +x "$W/queue2.sh"
sudo systemd-run --unit=x8-queue2 --uid="$USER" --working-directory="$W" --setenv=HOME="$HOME" -- "$W/queue2.sh"
sleep 100
systemctl is-active x8-queue2 x8-publish; tail -4 "$W/queue.log"; tail -1 "$W/runs/z1.log"; tail -1 "$W/runs/z2.log"; uptime
