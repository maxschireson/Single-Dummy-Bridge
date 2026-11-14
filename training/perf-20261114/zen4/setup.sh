#!/usr/bin/env bash
# P02 (PR #35): set up the perf session's Zen 4 measurement on a fresh box, everything under ~/perf.
#   setup.sh COMMIT      COMMIT: a commit of perf/stu-20261114
# Own venv (numpy 2.5.4 and torch's CPU build, as the loop's venv-t; h5py for the capsule's bidder), own checkout, DDS,
# the claim solver from research/sure-trick-table-20261112 at 2e6ed6d, the capture capsule's recovery folder from
# arena-gen6-gen7-capture-feed at 8833c62, the repository's nets and round 4c's rollout net (sha256 e4b689c8...).
set -euo pipefail
COMMIT=$1
P=$HOME/perf; S=$P/src; mkdir -p "$P/bin" "$P/runs"
REPO=https://github.com/maxschireson/Single-Dummy-Bridge
[ -x "$P/venv/bin/python" ] || python3 -m venv "$P/venv"
"$P/venv/bin/pip" install -q numpy==2.5.4 h5py 2>&1 | tail -1
"$P/venv/bin/pip" install -q torch --index-url https://download.pytorch.org/whl/cpu 2>&1 | tail -1
PY=$P/venv/bin/python
"$PY" -c "import numpy, torch, h5py; print('numpy', numpy.__version__, 'torch', torch.__version__, 'h5py', h5py.__version__, 'cpu', torch.backends.cpu.get_cpu_capability())"
if [ ! -d "$S/.git" ]; then git init -q "$S" && git -C "$S" remote add origin "$REPO"; fi
git -C "$S" fetch -q --depth 5 origin perf/stu-20261114 && git -C "$S" checkout -q "$COMMIT"
git -C "$S" log -1 --format='source %h %s' | cut -c1-120
T=$(mktemp -d); git -C "$T" init -q; git -C "$T" fetch -q --depth 1 "$REPO" research/sure-trick-table-20261112
git -C "$T" show 2e6ed6d:experiments/sure_tricks/sure.cpp > "$P/bin/sure.cpp" 2>/dev/null || git -C "$T" show FETCH_HEAD:experiments/sure_tricks/sure.cpp > "$P/bin/sure.cpp"
rm -rf "$T"; g++ -O2 -march=native -std=c++17 -o "$P/bin/sure_cpp" "$P/bin/sure.cpp"
cd "$S"
"$PY" scripts/build_dds.py > "$P/build_dds.log" 2>&1 && tail -1 "$P/build_dds.log"
for d in models/cardplay/hand-fit-scorer-v0-2026-11-11 models/cardplay/gen7-policy-v4.1-2026-11-12; do (cd "$d" && "$PY" restore.py | tail -1); done
bash training/rollout-loop-20261113/get_net.sh 4c e4b689c87db2f56b98221a491757dbf348ddaea066e016f06a9331fc671197f2
if [ ! -e "$P/capsule/recovery/manifest.json" ]; then
  T=$(mktemp -d); git -C "$T" init -q; git -C "$T" remote add origin "$REPO"
  git -C "$T" config core.sparseCheckout true; printf 'recovery/\n!recovery/episodes/\n!recovery/receipts/\n' > "$T/.git/info/sparse-checkout"
  git -C "$T" fetch -q --depth 1 --filter=blob:none origin arena-gen6-gen7-capture-feed && git -C "$T" checkout -q FETCH_HEAD
  mkdir -p "$P/capsule" && mv "$T/recovery" "$P/capsule/" && rm -rf "$T"
fi
echo "capsule $(du -sh "$P/capsule/recovery" | cut -f1), manifest $(sha256sum "$P/capsule/recovery/manifest.json" | cut -c1-16)"
export SURE_BIN=$P/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
rm -rf "$P/runs/smoke"
timeout 900 "$PY" scripts/x8_match.py --source "$P/capsule/recovery" --bots configs/loop-bots.json --pair stu4c-psta~stu4c-pstb \
  --deals 1 --first 0 --seed 777 --workers 1 --episodes --one-room --out "$P/runs/smoke" 2>&1 | tail -1
df -h ~ | tail -1; free -g | head -2; date -u +%FT%TZ
