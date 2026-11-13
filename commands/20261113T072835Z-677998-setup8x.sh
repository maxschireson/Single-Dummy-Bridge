# boxctl: timeout=60
# azure1: set up 8X v3 (Max, 07:1x UTC: azure1 goes to 8X v3 when its last Gen 8 cohort is played out): a checkout of
# feature/gen8x-arena-20261113, DDS, models, sure_cpp, the exclusion and played lists. Prepares nothing. Unit setup8x; log ~/work/gen8x/setup.log.
set -euo pipefail
[ "$BOXCTL_BOX" = azure1 ] || { echo "this command is for azure1"; exit 1; }
G=$HOME/work/gen8x; mkdir -p "$G"
cat > "$G/setup.sh" <<'EOF_SETUP'
#!/usr/bin/env bash
set -uo pipefail
W=$HOME/work; G=$W/gen8x; PY=$W/venv/bin/python; SRC=$W/sdb-gen8x
say() { echo "$(date -u +%T) $*"; }
say "load $(cut -d' ' -f1-3 /proc/loadavg); memory available $(free -m | awk 'NR==2{print $7}') MB"
if [ ! -d "$SRC/.git" ]; then git init -q "$SRC" && git -C "$SRC" remote add origin https://github.com/maxschireson/Single-Dummy-Bridge; fi
git -C "$SRC" fetch -q --depth 50 origin feature/gen8x-arena-20261113 && git -C "$SRC" checkout -q FETCH_HEAD || { say "checkout failed"; exit 1; }
say "checkout: $(git -C "$SRC" log -1 --format='%H %s' | cut -c1-120)"
cd "$SRC"
for r in models/*/*/restore*.py; do (cd "$(dirname "$r")" && nice "$PY" "$(basename "$r")" >/dev/null 2>/tmp/restore8x.err) || say "FAILED $r: $(tail -1 /tmp/restore8x.err)"; done
nice "$PY" scripts/build_dds.py >/dev/null 2>&1 || true
[ -s bridge_harness/libbridge_dds.so ] && say "DDS built" || { say "DDS library was not built"; exit 1; }
ls models/cardplay/rollout-net-v1-20261113/ | tr '\n' ' '; echo
D=$(mktemp -d)
git clone -q --depth 1 --single-branch --branch research/sure-trick-table-20261112 https://github.com/maxschireson/Single-Dummy-Bridge "$D/s" || { say "sure clone failed"; exit 1; }
say "sure source: $(git -C "$D/s" log -1 --format='%h %s' | cut -c1-100)"
nice g++ -O2 -march=native -std=c++17 -o "$G/sure_cpp" "$D/s/experiments/sure_tricks/sure.cpp" && say "sure_cpp built: $(sha256sum "$G/sure_cpp" | cut -c1-16)" || { say "sure_cpp build failed"; exit 1; }
git -C "$D/s" rev-parse HEAD > "$G/sure_cpp.commit"
git clone -q --depth 1 --single-branch --branch transfer/rollout-net-v1-training-families-20261113 https://github.com/maxschireson/Single-Dummy-Bridge "$D/x" && cp "$D/x"/gen8x-v3-exclusions.json "$G/" && say "exclusions: $(sha256sum "$G/gen8x-v3-exclusions.json" | cut -c1-16), $("$PY" -c "import json,sys; print(len(json.load(open(sys.argv[1]))))" "$G/gen8x-v3-exclusions.json") families" || say "exclusions fetch failed"
git clone -q --depth 1 --single-branch --branch transfer/gen9-cohort-inputs-20261113 https://github.com/maxschireson/Single-Dummy-Bridge "$D/p" && cp "$D/p/played-families-20261113.json.gz" "$G/" && say "played list: $(sha256sum "$G/played-families-20261113.json.gz" | cut -c1-16)"
rm -rf "$D"
out=$(cd "$SRC" && env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 TF_CPP_MIN_LOG_LEVEL=3 SURE_BIN="$G/sure_cpp" nice "$PY" -m unittest discover -s tests -p "test_x8.py" 2>&1 | grep -E "^(Ran|OK|FAILED|ERROR:|FAIL:)" | tr '\n' ' ' | cut -c1-400)
say "tests test_x8.py: $out"
grep -n -E "'--fresh'" "$SRC/ops/prepare_gen7_alpha.py" >/dev/null && say "prepare has --fresh" || say "prepare has no --fresh yet"
say DONE
EOF_SETUP
chmod +x "$G/setup.sh"
systemctl is-active --quiet setup8x && { echo "setup8x already running"; exit 0; }
sudo systemctl reset-failed setup8x 2>/dev/null || true
sudo systemd-run --quiet --unit=setup8x --uid="$(id -un)" --setenv=HOME="$HOME" --property=StandardOutput=append:"$G/setup.log" --property=StandardError=append:"$G/setup.log" -- "$G/setup.sh"
sleep 40; echo "setup8x: $(systemctl is-active setup8x)"; tail -6 "$G/setup.log" | cut -c1-240
