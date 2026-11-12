# boxctl: timeout=2400
# Gen 7 phase 1, launch step 1 on this box: checkout at the go-ahead commit, model files, DDS, the Gen 7 tests.
# The pre-7 test match keeps running meanwhile; nothing here touches it.
set -uo pipefail
GO=fe382f9b91c3c91ea0950281be5d8bf8e25e82ac
W=$HOME/work; PY=$W/venv/bin/python; SRC=$W/sdb-gen7-arena
if [ ! -d "$SRC/.git" ]; then
  git init -q "$SRC" && git -C "$SRC" remote add origin https://github.com/maxschireson/Single-Dummy-Bridge
fi
git -C "$SRC" fetch -q --depth 1 origin "$GO" && git -C "$SRC" checkout -q FETCH_HEAD || { echo "could not check out $GO"; exit 1; }
echo "checkout: $(git -C "$SRC" log -1 --format='%H %s' | cut -c1-120)"
cd "$SRC"
for r in models/*/*/restore*.py; do
  (cd "$(dirname "$r")" && "$PY" "$(basename "$r")" >/dev/null 2>/tmp/restore.err) || echo "FAILED $r: $(tail -1 /tmp/restore.err)"
done
echo "policy v4 sha256: $(sha256sum models/cardplay/gen7-policy-v4-2026-11-11/gen7_policy_v4.npz | cut -c1-64)"
"$PY" scripts/build_dds.py >/dev/null 2>&1; ls -la bridge_harness/libbridge_dds.so | awk '{print "dds library:", $5, "bytes"}'
echo "dds library sha256: $(sha256sum bridge_harness/libbridge_dds.so | cut -c1-16) (pre-7 checkout: $(sha256sum $W/sdb-gen7/bridge_harness/libbridge_dds.so | cut -c1-16))"
start=$(date +%s)
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 TF_CPP_MIN_LOG_LEVEL=3 nice -n 5 "$PY" -m unittest discover -s tests -p "test_gen7*.py" 2>&1 | tail -4
echo "tests took $(( $(date +%s) - start ))s"
