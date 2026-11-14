#!/usr/bin/env bash
# Isolated smoke + diagnostic screen. STU_RUNTIME, STU_EXPERIMENT_OUT and SURE_BIN required.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${STU_EXPERIMENT_OUT:?}
PY=${STU_PYTHON:-python3}
mkdir -p "$OUT"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=''
"$PY" "$HERE/make_config.py" --bots "$STU_RUNTIME/configs/loop-bots.json" --out "$OUT/bots.json"
for phase in smoke screen; do
  if [ "$phase" = smoke ]; then count=16; first=0; else count=128; first=1000; fi
  for variant in reader guarantee flat32 recursive32 selective32; do
    run="$OUT/$phase-$variant"
    "$PY" "$HERE/match.py" --source "$HOME/work/loop/capsule/recovery" \
      --bots "$OUT/bots.json" --pair "rx-$variant~rx-control" \
      --seed 2026111401 --first "$first" --deals "$count" --workers 4 --recycle 4 \
      --common-only --episodes --out "$run" > "$OUT/$phase-$variant.log" 2>&1
    "$PY" - "$run" "$count" <<'PY'
import json, pathlib, sys
p=pathlib.Path(sys.argv[1]); s=json.loads((p/'summary.json').read_text())
if s['boards'] != int(sys.argv[2]) or s.get('failures',0):
    raise SystemExit('incomplete/failed run: '+str(s))
print(json.dumps(s),flush=True)
PY
    "$PY" "$HERE/summarize.py" "$OUT"
  done
done
date -u +%FT%TZ > "$OUT/FINISHED"
