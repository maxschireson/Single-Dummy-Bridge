# boxctl: timeout=90
set -euo pipefail
W="$HOME/work/rollout-experiments-20261114"
systemctl show stu-rollout-experiments -p ActiveState -p MainPID -p ExecStart
sudo systemctl stop stu-rollout-experiments
python3 - "$W" <<'PY'
import json,pathlib,sys,time
w=pathlib.Path(sys.argv[1])
runs={}
for d in (w/'runs').iterdir():
    if d.is_dir():
        p=d/'results.jsonl'
        runs[d.name]=dict(rows=len(p.read_text().splitlines()) if p.exists() else 0,episodes=len(list((d/'episodes').glob('*.json.gz'))))
note=dict(stopped=time.strftime('%FT%TZ',time.gmtime()),reason='PR41/43 cache/scheduling inconsistency; old recursive/selective results diagnostic only; no extension or adoption',interrupted_boards='possible; preserve episodes and logs; do not treat partial screen as complete',runs=runs)
(w/'runs/REVIEW_PAUSE.json').write_text(json.dumps(note,indent=2))
print(json.dumps(note),flush=True)
PY
systemctl show stu-rollout-experiments stu-rollout-publish loop-publish loop-rows -p Id -p ActiveState -p MainPID
