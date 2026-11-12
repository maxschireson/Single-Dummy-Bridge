# boxctl: timeout=1200
# Resume of 12-phase1 on a box where prepare, preflight and the publication checkout are already done.
# Gen 7 phase 1 on this box, launch steps 2 to 6 of docs/gen7_candidate_2026-11-11.md at the go-ahead commit:
# non-BEN plan, the capture-feed capsule as source, this box's own shard, preflight, then the collector and the
# standard feed publisher. Everything that can fail runs before the pre-7 test match is drained.
set -euo pipefail
BOX=$BOXCTL_BOX
GO=fe382f9b91c3c91ea0950281be5d8bf8e25e82ac
CAPSULE=8833c62f83687293ad6b3ebfa10b58d1a25961f7
N=8
case "$BOX" in azure1) K=0 ;; azure2) K=1 ;; azure3) K=2 ;; azure4) K=3 ;; *) echo "no shard assigned to $BOX"; exit 1 ;; esac
W=$HOME/work; PY=$W/venv/bin/python; SRC=$W/sdb-gen7-arena
RUN=$W/runs/gen7-phase1-$BOX; PUB=$W/publication/gen7-phase1-$BOX; BRANCH=arena-gen7-phase1-$BOX-feed
PLAN=configs/round7-candidate-phase1-nonben.json; WORKERS=8
CAPS="OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TF_NUM_INTRAOP_THREADS=1 TF_NUM_INTEROP_THREADS=1 TF_CPP_MIN_LOG_LEVEL=3"
SSH="ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20"

[ -e "$RUN/preflight.json" ] && [ -d "$PUB/.git" ] && [ -z "$(ls "$RUN/receipts")" ] || { echo "not in the prepared-and-unstarted state"; exit 1; }
cd "$SRC"
echo "== drain the pre-7 test match"
PRE7=$(ls -d "$W"/runs/g7s-vs-g6f-01 "$W"/runs/pre7-7s-vs-6f-* 2>/dev/null | head -1 || true)
if [ -n "$PRE7" ] && systemctl is-active --quiet pre7-match; then
  touch "$PRE7/STOP"
  for i in $(seq 1 60); do systemctl is-active --quiet pre7-match || break; sleep 5; done
  systemctl is-active --quiet pre7-match && { echo "pre-7 match did not drain in 5 minutes; leaving it and not starting the collector"; exit 1; }
fi
echo "pre-7 run: $(ls "$PRE7/receipts" 2>/dev/null | wc -l) boards, failures $(ls "$PRE7/failures" 2>/dev/null | wc -l); its publisher makes the last push by itself"

echo "== units"
U=$(id -un)
sudo tee /etc/systemd/system/arena-gen7.service >/dev/null <<UNIT
[Unit]
Description=Gen 7 phase 1 collector ($BOX, shard $K/$N)
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=900
StartLimitBurst=3

[Service]
User=$U
WorkingDirectory=$SRC
Environment=HOME=$HOME PYTHONUNBUFFERED=1 $CAPS
ExecStart=$PY -u ops/gen5_runtime.py --run $RUN --workers $WORKERS
StandardOutput=append:$RUN.collector.log
StandardError=append:$RUN.collector.log
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
UNIT
sudo tee /etc/systemd/system/arena-gen7-publish.service >/dev/null <<UNIT
[Unit]
Description=Gen 7 phase 1 feed publisher ($BOX, $BRANCH)
After=network-online.target
Wants=network-online.target

[Service]
User=$U
WorkingDirectory=$SRC
Environment=HOME=$HOME PYTHONUNBUFFERED=1 $CAPS
ExecStart=$PY -u ops/publish_gen5.py --run $RUN --publication $PUB
StandardOutput=append:$RUN.publisher.log
StandardError=append:$RUN.publisher.log
Restart=on-failure
RestartSec=60

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --now arena-gen7.service >/dev/null 2>&1
sleep 100
echo "collector: $(systemctl is-active arena-gen7); boards $(ls "$RUN/receipts" | wc -l); $(uptime | sed 's/.*load/load/')"
tail -2 "$RUN.collector.log" | cut -c1-160
echo "== first publication"
if env $CAPS "$PY" -u ops/publish_gen5.py --run "$RUN" --publication "$PUB" --once > "$W/runs/gen7-phase1-publish-once.log" 2>&1; then
  tail -1 "$W/runs/gen7-phase1-publish-once.log" | cut -c1-200
  git -C "$PUB" log -1 --format='pushed %h %s' | cut -c1-120
  sudo systemctl enable --now arena-gen7-publish.service >/dev/null 2>&1
  sleep 3; echo "publisher: $(systemctl is-active arena-gen7-publish)"
else
  echo "first publication FAILED (the collector keeps running; records are safe on the box):"; tail -8 "$W/runs/gen7-phase1-publish-once.log" | cut -c1-300
fi
"$PY" -c "import json; s=json.load(open('$RUN/state.json')); print('state:', s['completed'], 'of', s['target'], s['by_pair'])"
