# boxctl: timeout=1500
# boxctl: timeout=1500
# plan session (Max's instruction 12 Nov 06:46 UTC; see BOARD.md on box/coordination): checkout, models, solver and
# fork-pair data under ~/work/plan. Touches nothing outside ~/work/plan. Light: git fetches, restores, a two-file check.
set -uo pipefail
SHA=97eca3afca5bf9d6669d197a6ab2ead83759b0ee
W=$HOME/work; P=$W/plan; PY=$W/venv/bin/python; SRC=$P/src
mkdir -p "$P/runs" "$P/data" "$P/models"
if [ ! -d "$SRC/.git" ]; then git init -q "$SRC" && git -C "$SRC" remote add origin https://github.com/maxschireson/Single-Dummy-Bridge; fi
git -C "$SRC" fetch -q --depth 1 origin "$SHA" && git -C "$SRC" checkout -q FETCH_HEAD || { echo "could not check out $SHA"; exit 1; }
echo "checkout: $(git -C "$SRC" log -1 --format='%h %s' | cut -c1-100)"
cd "$SRC"
for r in models/cardplay/gen7-policy-*/restore*.py models/cardplay/hand-fit-scorer-v0-2026-11-11/restore.py models/cardplay/gen5-2026-11-10/restore_policy.py; do
  (cd "$(dirname "$r")" && "$PY" "$(basename "$r")" >/dev/null 2>/tmp/plan-restore.err) || echo "FAILED $r: $(tail -1 /tmp/plan-restore.err)"
done
sha256sum models/cardplay/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz | cut -c1-16 | sed 's/^/policy v4.1 sha256 starts /'
ls models/cardplay/gen7-policy-*/*.npz | wc -l | sed 's/^/policy files in the checkout: /'
[ -e bridge_harness/libbridge_dds.so ] || "$PY" scripts/build_dds.py >/dev/null 2>/tmp/plan-dds.err || { echo "DDS build failed: $(tail -2 /tmp/plan-dds.err)"; }
ls -la bridge_harness/libbridge_dds.so | awk '{print "dds library:", $5, "bytes"}'
"$PY" scripts/plan_fetch.py --branch arena-gen6-fast-selfplay-20261111-19bbdce5-feed --first 5214 --last 6774 --out "$P/data/fresh_g6sp" 2>&1 | tail -1
M=models/cardplay
NETS="v0=$M/gen7-policy-v0-2026-11-11/gen7_policy_v0.npz,v2=$M/gen7-policy-v2-2026-11-11/gen7_policy_v2.npz,v4=$M/gen7-policy-v4-2026-11-11/gen7_policy_v4.npz,v41=$M/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz"
echo "$NETS" > "$P/nets.txt"
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 nice -n 10 "$PY" scripts/plan_bench.py --episodes "$P/data/fresh_g6sp" --nets "$NETS" --sims "v41:top;v41:map" \
  --files 4 --workers 2 --out "$P/runs/check.json" 2>&1 | tail -2 | cut -c1-300
CAP=$W/capsule-gen7-capture/recovery
ls "$CAP/manifest.json" "$CAP/assets/bidding" 2>&1 | head -4
rm -rf "$P/runs/check-match"
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 BRIDGE_DDS_CACHE= nice -n 10 "$PY" scripts/plan_match.py --source "$CAP" --bots configs/plan-bots.json \
  --pair pm50-32-v41~7f-32-v41 --deals 2 --seed 7 --workers 2 --out "$P/runs/check-match" 2>&1 | tail -2 | cut -c1-300
"$PY" -c "import numpy, sys; print('python', sys.version.split()[0], 'numpy', numpy.__version__)"
echo "setup done on $BOXCTL_BOX: $(nproc) cores, $(uptime | sed 's/.*load/load/')"
