# boxctl: timeout=600
# boxctl: timeout=600
# x8 session, azure6 (Max, 04:12 UTC): 8X with 8Z's claim and randomization among equal cards (8x1-ft1, 5ec36f1), matched
# against Gen 8. Stop x3 (8xr0-ft1, superseded) and z4 (8Z against Gen 7.1, paused; it resumes from its results later) and give
# their four workers to x4 = 8x1-ft1~8p-32-v41 on the same deals (seed 131). z3 and z5 (the leverage pair) keep running at
# 5c77d79 in src; x4 runs from a copy, src2, at 5ec36f1 (built DDS and restored models carried over).
set -euo pipefail
COMMIT=5ec36f16e5f7ca833b3aa524b33fe6a78f15c60a
W=$HOME/work/x8; S=$W/src; S2=$W/src2
pkill -f -- "--out $W/runs/x3" || true
pkill -f -- "--out $W/runs/z4" || true
sleep 4
for z in x3 z4; do echo "$(date -u +%FT%TZ) $z stopped at $(wc -l < $W/runs/$z/results.jsonl) boards (x4 takes its workers, Max 04:12)" >> "$W/queue.log"; done
rm -rf "$S2"; cp -a "$S" "$S2"
git -C "$S2" fetch -q --depth 5 origin feature/gen8x-rollout-bot-20261113 && git -C "$S2" checkout -q "$COMMIT"
git -C "$S2" log -1 --format='src2 %h %s' | cut -c1-100
cat > "$W/queue5.sh" <<'Q'
#!/bin/bash
set -uo pipefail
W=$HOME/work/x8; S2=$W/src2; PY=$HOME/work/venv/bin/python
export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 BRIDGE_DDS_CACHE=
cd "$S2"
echo "$(date -u +%FT%TZ) start x4 (8x1-ft1~8p-32-v41, 4 workers) source $(git rev-parse --short HEAD)" >> "$W/queue.log"
"$PY" scripts/x8_match.py --feature-forks --source $HOME/work/capsule-gen7-capture/recovery --bots configs/x8-bots.json \
  --pair 8x1-ft1~8p-32-v41 --deals 1600 --seed 131 --workers 4 --out "$W/runs/x4" >> "$W/runs/x4.log" 2>&1
echo "$(date -u +%FT%TZ) end x4: exit $?" >> "$W/queue.log"
Q
chmod +x "$W/queue5.sh"
sudo systemd-run --unit=x8-queue5 --uid="$USER" --working-directory="$W" --setenv=HOME="$HOME" -- "$W/queue5.sh"
sed -i 's#^x3: 8xr0-ft1 (8X, the blend)#x4: 8x1-ft1 (8X with the claim and defenders mixing too, 5ec36f1) against 8p-32-v41, seed 131. z4 paused at 04:2x to give x4 its workers. x3: 8xr0-ft1 (8X, the blend)#' "$W/publish.sh"
cp "$S2/scripts/x8_forks.py" "$W/bin/x8_forks.py"
sudo systemctl restart x8-publish
sleep 150
systemctl is-active x8-queue4 x8-queue5 x8-publish; tail -5 "$W/queue.log"; tail -2 "$W/runs/x4.log" | cut -c1-200
ps -eo args | grep "[x]8_match.py" | grep -o "runs/[a-z0-9]*" | sort | uniq -c; uptime
