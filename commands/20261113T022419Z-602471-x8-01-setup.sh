# boxctl: timeout=2400
# boxctl: timeout=2400
# x8 session: set up ~/work/x8 on azure6 (Max's authority, 02:20 UTC 13 Nov): own checkout, DDS and sure_cpp builds, models,
# a two-board smoke match. Reads g7's venv and capsule copy; touches nothing else.
set -euo pipefail
COMMIT=bb8506640cc5b3dc0dcc802ef224d5d74aaa7158
W=$HOME/work/x8; S=$W/src; PY=$HOME/work/venv/bin/python
mkdir -p "$W/runs" "$W/bin"
if [ ! -d "$S/.git" ]; then git init -q "$S" && git -C "$S" remote add origin https://github.com/maxschireson/Single-Dummy-Bridge; fi
git -C "$S" fetch -q --depth 5 origin feature/gen8x-rollout-bot-20261113 && git -C "$S" checkout -q "$COMMIT"
git -C "$S" log -1 --format='source %h %s' | cut -c1-120
# the claim solver, from its research branch
T=$(mktemp -d); git -C "$T" init -q; git -C "$T" fetch -q --depth 1 https://github.com/maxschireson/Single-Dummy-Bridge research/sure-trick-table-20261112
git -C "$T" show FETCH_HEAD:experiments/sure_tricks/sure.cpp > "$W/bin/sure.cpp"; rm -rf "$T"
g++ -O2 -march=native -std=c++17 -o "$W/bin/sure_cpp" "$W/bin/sure.cpp"
echo '0 0 8000000003 20008004000 1000400201c 3 3 2 4' | "$W/bin/sure_cpp" --value
cd "$S"
"$PY" scripts/build_dds.py > "$W/build_dds.log" 2>&1 && tail -1 "$W/build_dds.log"
for d in models/cardplay/hand-fit-scorer-v0-2026-11-11 models/cardplay/gen7-policy-v4.1-2026-11-12 models/cardplay/rollout-net-v1-20261113; do (cd $d && "$PY" restore.py | tail -1); done
(cd models/cardplay/gen5-2026-11-10 && "$PY" restore_policy.py | tail -1)
export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 BRIDGE_DDS_CACHE=
rm -rf "$W/runs/smoke"
timeout 1200 "$PY" scripts/x8_match.py --feature-forks --source $HOME/work/capsule-gen7-capture/recovery --bots configs/x8-bots.json \
  --pair 8xr0-ft1~8p-32-v41 --deals 4 --first 2000 --seed 131 --workers 4 --out "$W/runs/smoke" 2>&1 | tail -2 | cut -c1-300
"$PY" scripts/x8_forks.py "$W/runs/smoke" | head -3
