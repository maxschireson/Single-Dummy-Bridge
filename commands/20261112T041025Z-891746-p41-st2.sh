# boxctl: timeout=60
P=$HOME/work/p41; $HOME/work/venv/bin/python - <<'PY'
import json, os
m = json.load(open(os.path.expanduser('~/work/p41/data/fetch1.json')))
print('fetch1 finished', m['finished_utc'], 'new', m['new_blobs'])
for k, v in sorted(m['branches'].items()):
    print(f"{k} {v['episodes']} new={v['new']} tip={v['tip_time']}")
PY
tail -2 $P/logs/buildA.log | cut -c1-160; date -u +%T
