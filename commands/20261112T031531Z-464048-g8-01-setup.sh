# boxctl: timeout=1500
# boxctl: timeout=1500
# Gen 8 prototype (g8 chat, Max's instruction 12 Nov 02:38 UTC): checkout and models under ~/work/g8.
# Touches nothing outside ~/work/g8. Light: a git fetch, model restores, a two-board check on two cores.
set -uo pipefail
SHA=af701a3a78d758c67eac1e9880524dec87c37aa5
W=$HOME/work; G=$W/g8; PY=$W/venv/bin/python; SRC=$G/src; CAP=$W/capsule-gen7-capture/recovery
mkdir -p "$G/runs"
if [ ! -d "$SRC/.git" ]; then git init -q "$SRC" && git -C "$SRC" remote add origin https://github.com/maxschireson/Single-Dummy-Bridge; fi
git -C "$SRC" fetch -q --depth 1 origin "$SHA" && git -C "$SRC" checkout -q FETCH_HEAD || { echo "could not check out $SHA"; exit 1; }
echo "checkout: $(git -C "$SRC" log -1 --format='%h %s' | cut -c1-100)"
cd "$SRC"
for r in models/cardplay/gen7-policy-*/restore*.py; do
  (cd "$(dirname "$r")" && "$PY" "$(basename "$r")" >/dev/null 2>/tmp/g8-restore.err) || echo "FAILED $r: $(tail -1 /tmp/g8-restore.err)"
done
ls models/cardplay/gen7-policy-*/*.npz | wc -l | sed 's/^/policy files: /'
for d in "$W/sdb-gen7-arena" "$W/sdb-gen7"; do
  [ -e "$d/bridge_harness/libbridge_dds.so" ] && { cp "$d/bridge_harness/libbridge_dds.so" bridge_harness/; break; }
done
[ -e bridge_harness/libbridge_dds.so ] || "$PY" scripts/build_dds.py >/dev/null 2>&1
ls -la bridge_harness/libbridge_dds.so | awk '{print "dds library:", $5, "bytes"}'
"$PY" -c "import h5py, numpy; print('h5py', h5py.__version__, 'numpy', numpy.__version__)"
ls "$CAP/manifest.json" "$CAP/artifacts" | head -3
rm -rf "$G/runs/check"
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 nice -n 10 "$PY" scripts/gen8_match.py --source "$CAP" --bots configs/gen8-proto-bots.json \
  --pair 8s-32~7s-32 --deals 2 --seed 7 --workers 2 --out "$G/runs/check" 2>&1 | tail -3 | cut -c1-300
echo "setup done on $BOXCTL_BOX: $(uptime | sed 's/.*load/load/')"
