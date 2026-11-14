# boxctl: timeout=3000
# loop session (Max, 20:18 UTC: "Finish setting it up and put it to work on whatever is most productive"): set up azure7 as a
# loop box like azure2 (packages, the capture capsule, ~/work/loop with its own venv, checkout, sure_cpp and DDS builds, the
# models, rollout net v2, round 4c's net), then check two boards of Gen 8 self-play. Starts nothing long.
set -uo pipefail
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq && sudo apt-get install -y -qq build-essential python3-venv python3-dev git curl >/dev/null; g++ --version | head -1
mkdir -p ~/work && cd ~/work
REPO=https://github.com/maxschireson/Single-Dummy-Bridge
[ -d capsule-gen7-capture ] || git clone -q --depth 1 --branch arena-gen6-gen7-capture-feed "$REPO" capsule-gen7-capture
git -C capsule-gen7-capture log -1 --format='capsule %h' 
COMMIT=5addd826af8b10d7343df51ada528a7327d059b6
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113; mkdir -p "$W/runs" "$W/bin" "$W/capsule" "$W/pub"
[ -x "$W/venv/bin/python" ] || python3 -m venv "$W/venv"
"$W/venv/bin/pip" install -q --upgrade pip 2>&1 | tail -1
"$W/venv/bin/pip" install -q numpy==2.5.4 jax==0.12.0.1 jaxlib==0.12.0.1 optax==0.2.9 scipy==1.18.1 h5py==3.16.0 2>&1 | tail -2
PY=$W/venv/bin/python
"$PY" -c "import numpy, h5py, jax, optax; print('numpy', numpy.__version__, 'jax', jax.__version__, 'optax', optax.__version__)"
if [ ! -d "$S/.git" ]; then git init -q "$S" && git -C "$S" remote add origin "$REPO"; fi
git -C "$S" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S" checkout -q FETCH_HEAD
git -C "$S" log -1 --format='source %h'
D=$(mktemp -d); git -C "$D" init -q; git -C "$D" fetch -q --depth 1 "$REPO" research/sure-trick-table-20261112
git -C "$D" show FETCH_HEAD:experiments/sure_tricks/sure.cpp > "$W/bin/sure.cpp"; rm -rf "$D"
g++ -O2 -march=native -std=c++17 -o "$W/bin/sure_cpp" "$W/bin/sure.cpp" && echo "sure_cpp built"
cd "$S"
"$PY" scripts/build_dds.py > "$W/build_dds.log" 2>&1 && tail -1 "$W/build_dds.log"
for d in models/cardplay/hand-fit-scorer-v0-2026-11-11 models/cardplay/gen7-policy-v4.1-2026-11-12 models/cardplay/gen7-policy-v4-2026-11-11 models/cardplay/gen7-policy-v0-2026-11-11 models/cardplay/rollout-net-v1-20261113; do
  (cd $d && "$PY" restore.py > /dev/null 2>&1) || echo "restore failed: $d"
done
(cd models/cardplay/gen5-2026-11-10 && "$PY" restore_policy.py > /dev/null 2>&1) || echo "restore failed: gen5"
mkdir -p models/cardplay/rollout-net-v2-20261113
D=$(mktemp -d); git -C "$D" init -q; git -C "$D" fetch -q --depth 1 "$REPO" transfer/rollout-net-v2-20261113
git -C "$D" show FETCH_HEAD:runs/w768/policy_epoch5.npz > models/cardplay/rollout-net-v2-20261113/policy_epoch5.npz; rm -rf "$D"
sha256sum models/cardplay/rollout-net-v2-20261113/policy_epoch5.npz | cut -c1-20
bash training/rollout-loop-20261113/get_net.sh 4c e4b689c87db2f56b98221a491757dbf348ddaea066e016f06a9331fc671197f2 2>&1 | tail -1
[ -e "$W/capsule/recovery/manifest.json" ] || cp -a "$HOME/work/capsule-gen7-capture/recovery" "$W/capsule/"
sha256sum "$W/capsule/recovery/manifest.json" | cut -c1-16
export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
rm -rf "$W/runs/pf-g8"
timeout 900 "$PY" scripts/x8_match.py --source "$W/capsule/recovery" --bots configs/loop-bots.json --pair g8-greedy0~g8-passive0 --deals 4 --first 0 --seed 9000 --workers 4 --episodes --one-room --out "$W/runs/pf-g8" 2>&1 | tail -1 | cut -c1-140
ls "$W/runs/pf-g8/episodes" | wc -l; rm -rf "$W/runs/pf-g8"
nproc; free -g | sed -n 2p; df -h ~ | tail -1; date -u +%FT%TZ
