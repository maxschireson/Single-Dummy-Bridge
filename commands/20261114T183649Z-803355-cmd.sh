# boxctl: timeout=420
# loop session (Max, 17:43 UTC: "Do we need a wider net?"): the pool-trained net (v2: 768 wide, 5 epochs on the pool's 30.4M
# rows) gives up as much on rows it was trained on as on held-out rows (bot by bot: log-loss 0.434/0.455, 0.438/0.458,
# 0.443/0.442; tricks given up 0.018/0.020, 0.022/0.022, 0.023/0.021), so at this size more rows cannot help it much and
# the net itself is the first thing to test. This box holds the pool's rows: its Gen 8 collection stops (azure1 and azure3
# collect Gen 8) and a unit (loop-width) trains v2's recipe at twice the width (1,536: four times the parameters) on the
# same rows, scored each epoch on the same held-out deals as v2. When it ends the collection starts again.
set -euo pipefail
W=$HOME/work/loop; S=$W/src; S2=$W/src-lc; T=training/rollout-loop-20261113; D=$HOME/work/plan/rnet2w/data
[ -d "$S2/.git" ] && [ -f "$S2/scripts/train_rollout_net.py" ]
tail -n 2 "$W/runs.log" | cut -c1-150
sudo systemctl stop loop-collect loop-collect-b 2>/dev/null || true; sleep 3; pkill -u "$USER" -f scripts/x8_match.py 2>/dev/null || true
mkdir -p "$W/exp-width" "$W/pub/exp-width"
cat > "$W/width.sh" <<'EOS'
#!/usr/bin/env bash
W=$HOME/work/loop; S=$W/src; S2=$W/src-lc; T=training/rollout-loop-20261113; D=$HOME/work/plan/rnet2w/data; PY=$W/venv/bin/python
V2=models/cardplay/rollout-net-v2-20261113/policy_epoch5.npz
cd "$S2"; export OPENBLAS_NUM_THREADS=8 OMP_NUM_THREADS=8 MKL_NUM_THREADS=8
echo "$(date -u +%FT%TZ) width test begins: v2's recipe at 1,536 wide on the pool's rows (the collection is paused)" >> "$W/runs.log"
nice -n 5 "$PY" scripts/train_rollout_net.py --data "$D/train.npz" --all-train --val-data "$D/freshB.npz" --kind suit --width 1536 --epochs 5 \
  --save-epochs --compare "$V2" --out "$W/exp-width/w1536" > "$W/exp-width/w1536.log" 2>&1
rc=$?
cp -f "$W/exp-width/w1536.log" "$W/exp-width/w1536/metrics.json" "$W/pub/exp-width/" 2>/dev/null
echo "$(date -u +%FT%TZ) width test ended: exit $rc; the collection starts again" >> "$W/runs.log"
sudo systemctl reset-failed loop-collect loop-collect-b 2>/dev/null
sudo systemd-run --unit=loop-collect --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$S/$T/chain.sh" "$S/$T/jobs-azure5.txt"
EOS
sudo systemctl stop loop-width 2>/dev/null || true; sudo systemctl reset-failed loop-width 2>/dev/null || true
sudo systemd-run --unit=loop-width --uid="$USER" --working-directory="$S2" --setenv=HOME="$HOME" -- bash "$W/width.sh"
sleep 330
echo "width: $(systemctl is-active loop-width || true)"; grep -v Warning "$W/exp-width/w1536.log" | tail -n 4 | cut -c1-200; free -g | sed -n 2p; uptime | cut -c1-75; date -u +%FT%TZ
