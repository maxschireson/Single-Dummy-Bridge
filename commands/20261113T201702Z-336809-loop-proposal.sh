# boxctl: timeout=1500
# boxctl: timeout=1500
# loop session: the uniform-proposal efficiency of the layout reader's early decisions, on 30 boards of sp0 (read-only,
# one process at Nice 10 beside the collection, from a second checkout so the collection's source is untouched).
set -euo pipefail
W=$HOME/work/loop; S2=$W/src-lc; PY=$W/venv/bin/python
[ -d "$S2/.git" ] || git clone -q --depth 5 --branch research/rollout-loop-20261113 https://github.com/maxschireson/Single-Dummy-Bridge "$S2"
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q d7db140ab764d27bcb700fa9ca75fb8eeaa7afcc
for d in bridge_harness/libbridge_dds.so models/cardplay; do [ -e "$S2/$d" ] && [ ! -L "$S2/$d" ] && rm -rf "$S2/$d"; ln -sfn "$W/src/$d" "$S2/$d"; done
cd "$S2"; export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
mkdir -p /tmp/eps30 && rm -f /tmp/eps30/* && ls "$W/runs/sp0/episodes" | head -30 | while read f; do ln -sf "$W/runs/sp0/episodes/$f" /tmp/eps30/; done
timeout 1300 nice -n 10 "$PY" training/rollout-loop-20261113/bench/proposal.py /tmp/eps30 --boards 30 2>&1 | tail -12
