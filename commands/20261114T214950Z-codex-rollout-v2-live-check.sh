# boxctl: timeout=60
set -euo pipefail
W="$HOME/work/rollout-experiments-20261114"
systemctl show stu-rollout-v2-smokes stu-rollout-v2-publish -p Id -p ActiveState -p MainPID
python3 - "$W/runs-v2-d82f9a7" <<'PY'
import json,pathlib,sys
p=pathlib.Path(sys.argv[1])
for x in p.glob('*.log'):
    print(x.name, x.read_text()[-2500:])
for x in p.glob('*/summary.json'):
    s=json.loads(x.read_text()); print(x.parent.name,s['boards'],s['failures'],s.get('driver_failure'))
PY
