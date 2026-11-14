# boxctl: timeout=1500
# boxctl: timeout=1500
# loop session (read-only, Nice 10, second checkout, 2 workers): where the tricks go by double dummy, on azure1's records of
# SiD (rollout, net lead) Stu R3 against Gen 8 card play (l3-p, deals 500 to 999; all 500 boards).
set -euo pipefail
W=$HOME/work/loop; S2=$W/src-lc; PY=$W/venv/bin/python
[ -d "$S2/.git" ] || git clone -q --depth 5 --branch research/rollout-loop-20261113 https://github.com/maxschireson/Single-Dummy-Bridge "$S2"
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q bb0affe370551137830009e4adda4b22380d6ec1
for d in bridge_harness/libbridge_dds.so models/cardplay; do [ -e "$S2/$d" ] && [ ! -L "$S2/$d" ] && rm -rf "$S2/$d"; ln -sfn "$W/src/$d" "$S2/$d"; done
cd "$S2"; export BRIDGE_DDS_CACHE=
ls "$W/runs/l3-p/episodes" | wc -l
time nice -n 10 "$PY" training/rollout-loop-20261113/bench/dd_ledger.py "$W/runs/l3-p/episodes" --workers 2
tail -n 2 "$W/runs.log" | cut -c1-150; date -u +%FT%TZ
