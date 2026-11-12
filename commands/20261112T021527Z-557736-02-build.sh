# boxctl: timeout=3600
# Restore split model files, build DDS, run the Gen 7 tests.
set -uo pipefail
cd ~/work/sdb-gen7 || exit 1
PY=~/work/venv/bin/python
echo "== restore model files"
for r in models/*/*/restore*.py; do
  if (cd "$(dirname "$r")" && "$PY" "$(basename "$r")" >/dev/null 2>/tmp/restore.err); then echo "ok     $r"; else echo "FAILED $r: $(tail -1 /tmp/restore.err)"; fi
done
echo "== DDS"
start=$(date +%s); "$PY" scripts/build_dds.py 2>&1 | tail -2; echo "build took $(( $(date +%s) - start ))s"
ls -la bridge_harness/libbridge_dds.so || exit 1
echo "== Gen 7 tests"
start=$(date +%s); "$PY" -m unittest discover -s tests -p "test_gen7*.py" 2>&1 | tail -4; echo "tests took $(( $(date +%s) - start ))s"
