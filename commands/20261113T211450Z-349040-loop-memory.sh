# boxctl: timeout=1800
# boxctl: timeout=1800
# loop session: why the collection's sp0 workers grow to 3-4 GB and are killed for memory (BrokenProcessPool on azure1,
# 3, 6): two probe processes beside the collection (Nice 10, one core each, from the second checkout), 22 boards of pure
# Stu's self-play each, resident memory after every board; one with the nets in bf16 as the collection, one in fp32.
set -euo pipefail
W=$HOME/work/loop; S2=$W/src-lc; PY=$W/venv/bin/python
[ -d "$S2/.git" ] || git clone -q --depth 5 --branch research/rollout-loop-20261113 https://github.com/maxschireson/Single-Dummy-Bridge "$S2"
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q f423fd05c5165f5fabaf5db01cfa7123e3a0b569
for d in bridge_harness/libbridge_dds.so models/cardplay; do [ -e "$S2/$d" ] && [ ! -L "$S2/$d" ] && rm -rf "$S2/$d"; ln -sfn "$W/src/$d" "$S2/$d"; done
cd "$S2"; export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
free -m | sed -n 1,2p
BRIDGE_NET_BF16=1 timeout 1500 nice -n 10 "$PY" training/rollout-loop-20261113/bench/memory.py --boards 22 --first 900000 > /tmp/mem-bf16.txt 2>&1 &
BRIDGE_NET_BF16=0 timeout 1500 nice -n 10 "$PY" training/rollout-loop-20261113/bench/memory.py --boards 22 --first 900000 > /tmp/mem-fp32.txt 2>&1 &
wait
grep -v Warning /tmp/mem-bf16.txt | tail -24; echo; grep -v Warning /tmp/mem-fp32.txt | tail -24
free -m | sed -n 1,2p; date -u +%FT%TZ
