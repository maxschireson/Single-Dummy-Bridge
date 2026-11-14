# boxctl: timeout=90
set -euo pipefail
W="$HOME/work/rollout-experiments-20261114"
python3 - "$W" <<'PY'
from pathlib import Path
import sys
w=Path(sys.argv[1])
for p in (w/'runs').glob('*/results.jsonl'):
    if p.stat().st_size: raise RuntimeError('Boards already exist; do not alter this launch')
PY
sudo systemctl stop stu-rollout-experiments
cp "$W/run.sh" "$W/run-attempt0.sh"
python3 - "$W/run.sh" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); lines=p.read_text().splitlines()
matches=[i for i,line in enumerate(lines) if line.startswith("open(p,'w').write(json.dumps(b,indent=2)")]
assert len(matches)==1
lines[matches[0]]="open(p,'w').write(json.dumps(b,indent=2))"
p.write_text(chr(10).join(lines)+chr(10))
PY
if [ -d "$W/runs" ]; then mv "$W/runs" "$W/runs-attempt0"; fi
mkdir -p "$W/runs"
sudo systemctl start stu-rollout-experiments
cat "$W/drain-status.json"
systemctl show stu-rollout-experiments stu-rollout-publish loop-collect -p Id -p ActiveState -p MainPID
