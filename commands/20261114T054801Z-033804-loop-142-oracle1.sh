# boxctl: timeout=2400
# boxctl: timeout=2400
# loop session (read-only, Nice 10, second checkout, 2 workers): where SiD's early tricks go. At SiD (rollout, net lead) Stu
# R3's rollout decisions to trick 4 in its match against Gen 8 (l3-p, the first 120 boards), its card on layouts it draws
# again (control) and when every layout it rolls out is the deal as it lay (oracle), rated by double dummy.
set -euo pipefail
W=$HOME/work/loop; S2=$W/src-lc; PY=$W/venv/bin/python
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q 37f1c902093a2db6791aea8b0d647e5e48b45fe1
for d in bridge_harness/libbridge_dds.so models/cardplay; do [ -e "$S2/$d" ] && [ ! -L "$S2/$d" ] && rm -rf "$S2/$d"; ln -sfn "$W/src/$d" "$S2/$d"; done
cd "$S2"; export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
time timeout 2200 nice -n 10 "$PY" training/rollout-loop-20261113/bench/oracle_layout.py "$W/runs/l3-p" --source "$W/capsule/recovery" --tables 120 --to-trick 4 --copies 64 --workers 2 2>&1 | grep -v Warning | tail -12
tail -n 1 "$W/runs.log" | cut -c1-140; date -u +%FT%TZ
