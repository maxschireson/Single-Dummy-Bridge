# Stage `build` of chain.sh (sourced): the training set, v2's rows with the labels joined, in $SHARDS parts, merged.
d=$W/shards; mkdir -p "$d"
if [ ! -f "$d/.split" ]; then
  "$PY" - "$d" "$SHARDS" "$W/eps" <<'PYS'
import os, sys
from pathlib import Path
d, k = Path(sys.argv[1]), int(sys.argv[2])
files = sorted(Path(sys.argv[3]).glob('*.json.gz'), key=lambda f: f.name)
for i in range(k):
    (d / f's{i:02d}').mkdir(exist_ok=True)
    for f in files[i * len(files) // k:(i + 1) * len(files) // k]:
        if not (d / f's{i:02d}' / f.name).exists():
            os.symlink(f, d / f's{i:02d}' / f.name)
print(len(files), 'episodes in', k, 'parts', flush=True)
PYS
  touch "$d/.split"
fi
for part in $(ls "$d" | grep -v npz); do
  [ -f "$d/$part.npz" ] && continue
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 "$PY" scripts/gen7_build_dataset.py --episodes "$d/$part" --scorer "$SCORER" --policy-only \
    --labels "$W/labels" --out "$d/$part.npz.tmp.npz" --workers "$WORKERS" >> "$W/logs/build.log" 2>&1 || stop "build $part failed: $(tail -2 "$W/logs/build.log" | cut -c1-300)"
  mv "$d/$part.npz.tmp.npz" "$d/$part.npz"
  log "built $part: $(tail -1 "$W/logs/build.log" | cut -c1-220)"
done
"$PY" $T/merge_sets.py "$W/data/train.npz" "$d"/s*.npz >> "$W/logs/build.log" 2>&1 || stop "merge failed: $(tail -2 "$W/logs/build.log" | cut -c1-300)"
log "set: $(tail -1 "$W/logs/build.log" | cut -c1-700)"
rm -rf "$d"
