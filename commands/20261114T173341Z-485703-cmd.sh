# boxctl: timeout=900
# loop session (Max, 17:11 UTC: other rollout mechanisms?): a small test of bench/seat_variants.py on this box's self-play
# records (4 boards of sp3s, every second decision), from a second checkout so the collection's is not touched; two
# workers at Nice 10 beside the collection.
set -euo pipefail
W=$HOME/work/loop; S2=$W/src-lc; PY=$W/venv/bin/python; SHA=09a90b75fdf8c7c5cd09aa742cb44be148d0aebb
if [ ! -d "$S2/.git" ]; then git clone -q --depth 5 --branch research/rollout-loop-20261113 "$(git -C "$W/src" remote get-url origin)" "$S2"; fi
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q -f "$SHA"
for d in bridge_harness/libbridge_dds.so models/cardplay; do if [ -e "$S2/$d" ] && [ ! -L "$S2/$d" ]; then rm -rf "$S2/$d"; fi; ln -sfn "$W/src/$d" "$S2/$d"; done
cd "$S2"; export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
rm -f /tmp/sv-test.jsonl
time timeout 780 nice -n 10 "$PY" training/rollout-loop-20261113/bench/seat_variants.py "$W/runs/sp3s" --source "$W/capsule/recovery" --boards 4 --every 2 --workers 2 --out /tmp/sv-test.jsonl 2>&1 | grep -v Warning | tail -45 | cut -c1-200
wc -l /tmp/sv-test.jsonl; free -g | sed -n 2p; date -u +%T
