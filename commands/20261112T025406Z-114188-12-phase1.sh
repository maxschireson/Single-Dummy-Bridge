# boxctl: timeout=2400
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

[ "$(git -C "$SRC" rev-parse HEAD)" = "$GO" ] || { echo "source is not at the go-ahead commit"; exit 1; }
[ "$(git -C "$W/capsule-gen7-capture" rev-parse HEAD)" = "$CAPSULE" ] || { echo "capsule is not at $CAPSULE"; exit 1; }
[ -e "$RUN" ] && { echo "$RUN already exists; not overwriting"; exit 1; }
[ -e "$PUB" ] && { echo "$PUB already exists; not overwriting"; exit 1; }
if GIT_SSH_COMMAND="$SSH" git ls-remote --exit-code --heads git@github.com:maxschireson/Single-Dummy-Bridge.git "$BRANCH" >/dev/null 2>&1; then
  echo "branch $BRANCH already exists on GitHub; not publishing over it"; exit 1
fi

cd "$SRC"
echo "== prepare (shard $K/$N)"
"$PY" ops/prepare_gen7_alpha.py --source "$W/capsule-gen7-capture/recovery" --run "$RUN" --plan "$PLAN" --shard "$K/$N" > "$W/runs/gen7-phase1-prepare.json"
"$PY" - "$W/runs/gen7-phase1-prepare.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
tree = d['gen7']['7s-32']['tree'][0]
print('identity', d['identity'], '| target', d['target'], '| shard', d['shard'], '| pairs', d['allocation'])
print('tree: margin', tree['root_margin'], 'trust', tree['trust'], 'path', tree['path'], 'tricks', tree['tricks'], 'breadth', tree['breadth'], 'layouts', tree['layouts'], 'plain', tree['plain'])
assert (tree['root_margin'], tree['trust'], tree['path'], tree['tricks']) == (0.25, 0.3, 0.5, 3), 'not the authorized tree settings'
PYEOF
echo "== preflight"
start=$(date +%s)
env $CAPS "$PY" ops/smoke_gen7.py --run "$RUN" --out "$RUN/preflight.json" > /dev/null 2> "$W/runs/gen7-phase1-preflight.err" || { echo "preflight FAILED:"; tail -6 "$W/runs/gen7-phase1-preflight.err"; exit 1; }
"$PY" - "$RUN/preflight.json" <<'PYEOF'
import json, sys
r = json.load(open(sys.argv[1]))
print('preflight passed:', [(d.get('pair'), d.get('index'), d.get('decisions')) for d in r['deals']])
PYEOF
echo "preflight took $(( $(date +%s) - start ))s"

echo "== records for recovery"
cp "$PLAN" "$RUN/plan.json"
"$PY" -m pip freeze 2>/dev/null > "$RUN/runtime-requirements.txt"
"$PY" - "$RUN" "$BOX" "$K" "$N" "$GO" "$CAPSULE" "$WORKERS" "$BRANCH" <<'PYEOF'
import json, os, platform, sys, time
run, box, k, n, go, capsule, workers, branch = sys.argv[1:9]
import numpy, scipy, tensorflow as tf
cpu = next((l.split(':', 1)[1].strip() for l in open('/proc/cpuinfo') if l.lower().startswith('model name')), None)
env = dict(host=box, machine='Azure Standard_F8as_v6, 8 vCPUs, 32 GB', cpu=cpu, os=platform.platform(), python=sys.version.split()[0],
           packages=dict(tensorflow=tf.__version__, numpy=numpy.__version__, scipy=scipy.__version__),
           source_repository='https://github.com/maxschireson/Single-Dummy-Bridge', source_branch='feature/gen7-candidate-20261111', source_commit=go,
           source_run='arena-gen6-gen7-capture-feed recovery capsule at ' + capsule, plan='configs/round7-candidate-phase1-nonben.json',
           shard=f'{k}/{n}', workers=int(workers), threads='one BLAS, OpenMP and TensorFlow thread a worker', publication_branch=branch,
           supervision='systemd units arena-gen7 and arena-gen7-publish; no BEN server on this machine',
           operator='Claude session https://claude.ai/code/session_01N2EvxEiuqLC6xtt2hftSWZ, through the boxctl agent (docs/boxctl.md on feature/boxctl-20261112)')
json.dump(env, open(os.path.join(run, 'environment.json'), 'w'), indent=1)
json.dump(dict(launched_epoch=time.time(), authority='Max, 12 November 2026: include the four Azure boxes as Gen 7 collectors, following the GitHub instructions',
               notice='docs/gen7_candidate_2026-11-11.md at ' + go, steps='launch steps 1 to 6 of the notice', host=box, shard=f'{k}/{n}'),
          open(os.path.join(run, 'launch.json'), 'w'), indent=1)
PYEOF

echo "== publication checkout ($BRANCH)"
mkdir -p "$PUB" && git -C "$PUB" init -q && git -C "$PUB" checkout -q --orphan "$BRANCH"
git -C "$PUB" remote add origin git@github.com:maxschireson/Single-Dummy-Bridge.git
git -C "$PUB" config core.sshCommand "$SSH"
git -C "$PUB" config user.name "Claude"; git -C "$PUB" config user.email "noreply@anthropic.com"
cat > "$PUB/.git/hooks/commit-msg" <<'HOOK'
#!/bin/sh
grep -q "^Claude-Session:" "$1" || printf '\nCo-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01N2EvxEiuqLC6xtt2hftSWZ\n' >> "$1"
HOOK
chmod +x "$PUB/.git/hooks/commit-msg"

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
