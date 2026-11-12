# boxctl: timeout=1000
# boxctl: timeout=900
# plan session: a two-deal match on azure5 from a scratch checkout, to prove the capsule and h5py before the queued match.
set -uo pipefail
P=$HOME/work/plan; PY=$HOME/work/venv/bin/python; S=$P/smoke-src
if [ ! -d "$S/.git" ]; then git init -q "$S" && git -C "$S" remote add origin https://github.com/maxschireson/Single-Dummy-Bridge; fi
git -C "$S" fetch -q --depth 1 origin f80593e1a02d5587b6df3f534b21e301c133ca22 && git -C "$S" checkout -q FETCH_HEAD || { echo "checkout failed"; exit 1; }
cd "$S"
for r in models/cardplay/gen7-policy-*/restore*.py models/cardplay/hand-fit-scorer-v0-2026-11-11/restore.py models/cardplay/gen5-2026-11-10/restore_policy.py; do
  (cd "$(dirname "$r")" && "$PY" "$(basename "$r")" >/dev/null 2>/tmp/plan-restore.err) || echo "FAILED $r: $(tail -1 /tmp/plan-restore.err)"
done
[ -e bridge_harness/libbridge_dds.so ] || cp "$P/src/bridge_harness/libbridge_dds.so" bridge_harness/
rm -rf "$P/runs/smoke-match"
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 BRIDGE_DDS_CACHE= PYTHONPATH=$P/pylib nice -n 5 "$PY" scripts/plan_match.py --source "$P/capsule/recovery" --bots configs/plan-bots.json \
  --pair pr75-32-v41~7s-32-v41 --deals 2 --seed 7 --workers 2 --out "$P/runs/smoke-match" 2>&1 | tail -3 | cut -c1-300
