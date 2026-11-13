# boxctl: timeout=2400
# boxctl: timeout=2400
# loop session (Max, 08:23 UTC 13 Nov: "Take azure 3 and 5"): set up ~/work/loop on azure3 while the lanes are still up
# (a pip install and three small builds at Nice 10). Own venv, checkout, builds and capsule copy; nothing of g7's or
# g8's is changed. No match is started here.
set -euo pipefail
W=$HOME/work/loop; S=$W/src; mkdir -p "$W/runs" "$W/bin" "$W/capsule"
[ -x "$W/venv/bin/python" ] || python3 -m venv "$W/venv" || "$HOME/work/venv/bin/python" -m venv "$W/venv"
nice -n 10 "$W/venv/bin/pip" install -q numpy==2.5.4 jax==0.12.0.1 jaxlib==0.12.0.1 optax==0.2.9 scipy==1.18.1 h5py==3.16.0 2>&1 | tail -2
PY=$W/venv/bin/python
"$PY" -c "import numpy, h5py, jax, optax; print('numpy', numpy.__version__, 'h5py', h5py.__version__, 'jax', jax.__version__, 'optax', optax.__version__)"
COMMIT=79c18459f3455338ed7816c022b7a380ae62b890
if [ ! -d "$S/.git" ]; then git init -q "$S" && git -C "$S" remote add origin https://github.com/maxschireson/Single-Dummy-Bridge; fi
git -C "$S" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"
git -C "$S" log -1 --format='source %h %s' | cut -c1-120
T=$(mktemp -d); git -C "$T" init -q; git -C "$T" fetch -q --depth 1 https://github.com/maxschireson/Single-Dummy-Bridge research/sure-trick-table-20261112
echo "sure.cpp from $(git -C "$T" rev-parse --short FETCH_HEAD)"
git -C "$T" show FETCH_HEAD:experiments/sure_tricks/sure.cpp > "$W/bin/sure.cpp"; rm -rf "$T"
nice -n 10 g++ -O2 -march=native -std=c++17 -o "$W/bin/sure_cpp" "$W/bin/sure.cpp"
echo '0 0 8000000003 20008004000 1000400201c 3 3 2 4' | "$W/bin/sure_cpp" --value
sha256sum "$W/bin/sure.cpp" | cut -c1-20
cd "$S"
nice -n 10 "$PY" scripts/build_dds.py > "$W/build_dds.log" 2>&1 && tail -1 "$W/build_dds.log"
for d in models/cardplay/hand-fit-scorer-v0-2026-11-11 models/cardplay/gen7-policy-v4.1-2026-11-12 models/cardplay/gen7-policy-v4-2026-11-11 models/cardplay/gen7-policy-v0-2026-11-11 models/cardplay/rollout-net-v1-20261113; do (cd $d && "$PY" restore.py | tail -1); done
(cd models/cardplay/gen5-2026-11-10 && "$PY" restore_policy.py | tail -1)
mkdir -p models/cardplay/rollout-net-v2-20261113
T=$(mktemp -d); git -C "$T" init -q; git -C "$T" fetch -q --depth 1 https://github.com/maxschireson/Single-Dummy-Bridge transfer/rollout-net-v2-20261113
git -C "$T" show FETCH_HEAD:runs/w768/policy_epoch5.npz > models/cardplay/rollout-net-v2-20261113/policy_epoch5.npz; rm -rf "$T"
sha256sum models/cardplay/rollout-net-v2-20261113/policy_epoch5.npz models/cardplay/gen7-policy-v4-2026-11-11/gen7_policy_v4.npz models/cardplay/gen7-policy-v0-2026-11-11/gen7_policy_v0.npz | cut -c1-110
if [ ! -e "$W/capsule/recovery/manifest.json" ]; then C=$HOME/work/capsule-gen7-capture/recovery; echo "capsule $(du -sh "$C" | cut -f1)"; cp -a "$C" "$W/capsule/"; fi
ls "$W/capsule/recovery" | head -5 | tr '\n' ' '; echo
"$PY" - <<'PY'
import hashlib, json, os
m = os.path.expanduser('~/work/loop/capsule/recovery/manifest.json')
d = json.load(open(m)); print('capsule manifest sha256', hashlib.sha256(open(m, 'rb').read()).hexdigest()[:16], 'bots', sorted(d.get('bots', d.get('generations', {})))[:12])
PY
df -h ~ | tail -1; free -g | sed -n 2p; uptime; date -u +%FT%TZ
