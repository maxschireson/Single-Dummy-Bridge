#!/usr/bin/env bash
# Correctness smokes only; research screens require a separate reviewed launcher. STU_RUNTIME, STU_EXPERIMENT_OUT and SURE_BIN required.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${STU_EXPERIMENT_OUT:?}
PY=${STU_PYTHON:-python3}
mkdir -p "$OUT"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=''
"$PY" "$HERE/make_config.py" --bots "$STU_RUNTIME/configs/loop-bots.json" --out "$OUT/bots.json"
for phase in smoke; do
  count=16; first=2000
  for variant in flat32 recursive32 selective32; do
    run="$OUT/$phase-$variant"
    "$PY" "$HERE/match.py" --source "$HOME/work/loop/capsule/recovery" \
      --bots "$OUT/bots.json" --pair "rx2-$variant~rx2-control" \
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
