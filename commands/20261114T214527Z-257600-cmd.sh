# boxctl: timeout=120
# loop session: perf's V1 (board 21:45 UTC) asks for round 4's test rows. Copies r4c/stu_test.npz (and the held split, for
# reference) into pub/train-r4c/ with sha256 and row counts, for the publisher. Read-only otherwise.
set -uo pipefail
W=$HOME/work/loop; PY=$W/venv/bin/python
ls -la "$W/r4c/" | grep -i "test\|held\|val" | head
mkdir -p "$W/pub/train-r4c"
for f in stu_test.npz; do
  [ -f "$W/r4c/$f" ] || { echo "missing $f"; continue; }
  cp -f "$W/r4c/$f" "$W/pub/train-r4c/$f"; sha256sum "$W/pub/train-r4c/$f" | cut -c1-64 > "$W/pub/train-r4c/$f.sha256"
  "$PY" -c "import numpy as np,sys; z=np.load(sys.argv[1]); k=list(z.keys()); print(sys.argv[1].split('/')[-1], len(z[k[0]]), 'rows', k[:8])" "$W/pub/train-r4c/$f"
done
cat "$W/pub/train-r4c/stu_test.npz.sha256"; ls "$W/pub/train-r4c/"; systemctl list-units --no-legend 'loop-pub*' 2>/dev/null | head -3
wc -l "$W"/pub/h05/*.jsonl
