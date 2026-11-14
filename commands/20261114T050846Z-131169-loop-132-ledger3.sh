# boxctl: timeout=1500
# boxctl: timeout=1500
# loop session (read-only, Nice 10, second checkout, 1 worker beside the gate): where the tricks go by double dummy in the
# matches against BEN (200) on azure3: SiD (rollout) Stu R3 (b3-ps200), R0 (b0-ps200), the one-net bot (b3-pst200), Gen 8 (bg-200).
set -euo pipefail
W=$HOME/work/loop; S2=$W/src-lc; PY=$W/venv/bin/python
[ -d "$S2/.git" ] || git clone -q --depth 5 --branch research/rollout-loop-20261113 https://github.com/maxschireson/Single-Dummy-Bridge "$S2"
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q bb0affe370551137830009e4adda4b22380d6ec1
for d in bridge_harness/libbridge_dds.so models/cardplay; do [ -e "$S2/$d" ] && [ ! -L "$S2/$d" ] && rm -rf "$S2/$d"; ln -sfn "$W/src/$d" "$S2/$d"; done
cd "$S2"; export BRIDGE_DDS_CACHE=
for run in b3-ps200 b0-ps200 b3-pst200 bg-200; do
  echo "=== $run"; ls -d "$W"/runs/$run-[1-8]/episodes 2>/dev/null | wc -l
  nice -n 10 "$PY" training/rollout-loop-20261113/bench/dd_ledger.py $(ls -d "$W"/runs/$run-[1-8]/episodes) --workers 1 | tail -n +2
done
tail -n 2 "$W/runs.log" | cut -c1-150; date -u +%FT%TZ
