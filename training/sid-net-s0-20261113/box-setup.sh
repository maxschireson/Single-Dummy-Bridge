#!/bin/bash
# One-time setup of a box for training/sid-net-s0-20261113/chain.sh, and source updates later (run through boxctl).
#   bash box-setup.sh [BRANCH]      everything under ~/work/sidnet; nothing else on the box is touched
set -euo pipefail
B=${1:-research/sid-net-s0-20261113}; W=$HOME/work/sidnet; PY=$HOME/work/venv/bin/python
mkdir -p "$W"/{bin,logs,data,models,done}
cd "$W"
if [ ! -d src/.git ]; then
  git clone -q --depth 1 -b "$B" https://github.com/maxschireson/Single-Dummy-Bridge src
else
  git -C src fetch -q --depth 1 origin "$B" && git -C src reset -q --hard FETCH_HEAD
fi
cd src; echo "source $(git rev-parse --short HEAD) $(git log -1 --format=%s | cut -c1-80)"
g++ -O2 -march=native -std=c++17 -o "$W/bin/cells.new" experiments/sure_tricks/cells/cells.cpp && mv "$W/bin/cells.new" "$W/bin/cells"
g++ -O2 -march=native -std=c++17 -o "$W/bin/sure_cpp.new" experiments/sure_tricks/sure.cpp && mv "$W/bin/sure_cpp.new" "$W/bin/sure_cpp"
echo "sure_cpp check (must be value 0): $(echo '0 0 8000000003 20008004000 1000400201c 3 3 2 4' | "$W/bin/sure_cpp" --value | cut -c1-40)"
if [ ! -f "$W/models/hand_fit_v0.npz" ]; then
  "$PY" models/cardplay/hand-fit-scorer-v0-2026-11-11/restore.py > /dev/null
  cp models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz "$W/models/"
fi
echo "scorer sha256 $(sha256sum "$W/models/hand_fit_v0.npz" | cut -c1-16) (56e6444079d1451a expected)"
if [ ! -f "$W/models/rollout_v2_w768_epoch5.npz" ]; then
  rm -rf "$W/v2tmp"; git init -q "$W/v2tmp"
  git -C "$W/v2tmp" fetch -q --depth 1 https://github.com/maxschireson/Single-Dummy-Bridge transfer/rollout-net-v2-20261113
  git -C "$W/v2tmp" show FETCH_HEAD:runs/w768/policy_epoch5.npz > "$W/models/rollout_v2_w768_epoch5.npz"
  git -C "$W/v2tmp" show FETCH_HEAD:runs/w768/metrics.json > "$W/models/rollout_v2_w768_metrics.json"
  rm -rf "$W/v2tmp"
fi
echo "v2 net sha256 $(sha256sum "$W/models/rollout_v2_w768_epoch5.npz" | cut -c1-16), $(stat -c %s "$W/models/rollout_v2_w768_epoch5.npz") bytes"
"$PY" -c "import numpy; print('numpy', numpy.__version__)"
nproc; df -h "$HOME" | tail -1
