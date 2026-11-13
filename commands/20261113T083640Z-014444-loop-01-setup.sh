# boxctl: timeout=2400
# boxctl: timeout=2400
# loop session (Max, 08:23 UTC 13 Nov: "Take azure 3 and 5"): stop plan's job that started 74 s before its queue was frozen,
# then set up ~/work/loop (own venv, own checkout, own builds, a copy of the capsule). Nothing of plan's or p41's is changed.
set -euo pipefail
# 1. plan's rbc2b (queue line 40) started 08:33:34; the queue was frozen at 08:34:47 (queue.sh, pid 53065, still frozen).
#    To run rbc2b again later: sudo kill -CONT 53065; wait for "end rbc2b" in queue.log; echo 39 > ~/work/plan/queue.pos
pkill -TERM -f 'plan_reading_bound.py.*--skip-files 308' || true
sleep 6
pkill -KILL -f 'plan_reading_bound.py.*--skip-files 308' || true
sleep 1
echo "plan_reading_bound.py processes left: $(pgrep -f plan_reading_bound.py | wc -l); queue.sh state: $(ps -o stat= -p 53065 2>/dev/null)"
# 2. own folder and venv (the shared ~/work/venv has no h5py)
W=$HOME/work/loop; S=$W/src; mkdir -p "$W/runs" "$W/bin" "$W/capsule"
[ -x "$W/venv/bin/python" ] || python3 -m venv "$W/venv" || "$HOME/work/venv/bin/python" -m venv "$W/venv"
"$HOME/work/venv/bin/pip" freeze 2>/dev/null | grep -i -E '^(numpy|jax|jaxlib|optax|scipy)==' > "$W/req.txt" || true
echo h5py >> "$W/req.txt"; tr '\n' ' ' < "$W/req.txt"; echo
"$W/venv/bin/pip" install -q -r "$W/req.txt" 2>&1 | tail -2
PY=$W/venv/bin/python
"$PY" -c "import numpy, h5py, jax, optax; print('numpy', numpy.__version__, 'h5py', h5py.__version__, 'jax', jax.__version__, 'optax', optax.__version__)"
# 3. source: sidnet's branch tip (8X engine 1a779a9, plan's gen7_net.py, the label heads and the trainer)
COMMIT=24c80911c4cf1dec22e59ff273c68edb22c2fce9
if [ ! -d "$S/.git" ]; then git init -q "$S" && git -C "$S" remote add origin https://github.com/maxschireson/Single-Dummy-Bridge; fi
git -C "$S" fetch -q --depth 5 origin research/sid-net-s0-20261113 && git -C "$S" checkout -q "$COMMIT"
git -C "$S" log -1 --format='source %h %s' | cut -c1-120
# 4. the claim solver, from its research branch
T=$(mktemp -d); git -C "$T" init -q; git -C "$T" fetch -q --depth 1 https://github.com/maxschireson/Single-Dummy-Bridge research/sure-trick-table-20261112
echo "sure.cpp from $(git -C "$T" rev-parse --short FETCH_HEAD)"
git -C "$T" show FETCH_HEAD:experiments/sure_tricks/sure.cpp > "$W/bin/sure.cpp"; rm -rf "$T"
g++ -O2 -march=native -std=c++17 -o "$W/bin/sure_cpp" "$W/bin/sure.cpp"
echo '0 0 8000000003 20008004000 1000400201c 3 3 2 4' | "$W/bin/sure_cpp" --value
cmp -s "$W/bin/sure.cpp" "$HOME/work/plan/bin/sure.cpp" && echo "sure.cpp equals plan's copy" || echo "sure.cpp differs from plan's copy"
# 5. DDS and models
cd "$S"
"$PY" scripts/build_dds.py > "$W/build_dds.log" 2>&1 && tail -1 "$W/build_dds.log"
for d in models/cardplay/hand-fit-scorer-v0-2026-11-11 models/cardplay/gen7-policy-v4.1-2026-11-12 models/cardplay/rollout-net-v1-20261113; do (cd $d && "$PY" restore.py | tail -1); done
(cd models/cardplay/gen5-2026-11-10 && "$PY" restore_policy.py | tail -1)
mkdir -p models/cardplay/rollout-net-v2-20261113
T=$(mktemp -d); git -C "$T" init -q; git -C "$T" fetch -q --depth 1 https://github.com/maxschireson/Single-Dummy-Bridge transfer/rollout-net-v2-20261113
git -C "$T" show FETCH_HEAD:runs/w768/policy_epoch5.npz > models/cardplay/rollout-net-v2-20261113/policy_epoch5.npz
echo "rollout net v2 from transfer/rollout-net-v2-20261113 at $(git -C "$T" rev-parse --short FETCH_HEAD)"; rm -rf "$T"
sha256sum models/cardplay/rollout-net-v2-20261113/policy_epoch5.npz "$HOME/work/plan/nets/v2/policy_epoch5.npz" | cut -c1-100
"$PY" - <<'PY'
import numpy as np
z = np.load('models/cardplay/rollout-net-v2-20261113/policy_epoch5.npz', allow_pickle=True)
print('v2 arrays:', len(z.files), [k for k in z.files if not k.startswith(('w', 'b')) or 'bot' in k][:20])
for k in z.files:
    if 'vocab' in k or 'bot' in k or k in ('kind', 'meta'):
        v = z[k]; print(k, v.tolist() if v.size < 80 else v.shape)
PY
# 6. the capsule (base bots and their nets): a copy of plan's, so nothing of plan's is read during the runs
if [ ! -e "$W/capsule/recovery/manifest.json" ]; then echo "capsule $(du -sh "$HOME/work/plan/capsule/recovery" | cut -f1)"; cp -a "$HOME/work/plan/capsule/recovery" "$W/capsule/"; fi
ls "$W/capsule/recovery" | head -5 | tr '\n' ' '; echo
# 7. smoke: two boards of 8Z (the tested 8z-ft1) against itself with the full records kept
export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 BRIDGE_DDS_CACHE=
rm -rf "$W/runs/smoke0"
timeout 1200 "$PY" scripts/x8_match.py --source "$W/capsule/recovery" --bots configs/x8-bots.json --pair 8z-ft1~8z-ft1 --deals 2 --first 0 --seed 9000 --workers 2 --episodes --out "$W/runs/smoke0" 2>&1 | tail -3 | cut -c1-300
ls -la "$W/runs/smoke0" | head -12; ls -la "$W/runs/smoke0/episodes" 2>/dev/null | head -6
"$PY" - <<'PY'
import json, os
p = os.path.expanduser('~/work/loop/runs/smoke0/results.jsonl')
for l in open(p):
    r = json.loads(l)
    print({k: r[k] for k in ('index', 'contract', 'common', 'cpu') if k in r}, {k: v for k, v in (r.get('search', {}).get('candidate', {}).get('x8') or {}).items() if k in ('rollout', 'blend', 'search', 'moved', 'seconds')})
PY
df -h ~ | tail -1; uptime; date -u +%FT%TZ
