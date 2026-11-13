# boxctl: timeout=30
# Read-only (g7): the failure record of g7's stopped 8X v3 cohort on azure1, now the loop's box. Changes nothing.
R=$HOME/work/runs/gen8-x3-azure1; ls -la $R/failures | tail -3 | cut -c1-160
f=$(ls $R/failures | head -1); python3 - "$R/failures/$f" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
print({k: (str(v)[:300] if k not in ('traceback',) else None) for k, v in d.items()})
tb = d.get('traceback') or d.get('error') or ''
print(str(tb)[-1800:])
PY
grep -v -E "^\{\"completed" $HOME/work/gen8x/collector.log | tail -n 12 | cut -c1-240
