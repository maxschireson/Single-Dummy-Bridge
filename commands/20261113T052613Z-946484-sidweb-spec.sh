# boxctl: timeout=120
# boxctl: timeout=120
# sidweb (read-only): the full 8s-32 bot spec and systems map from the gen8-s7-azure1 manifest.
python3 - <<'PY'
import json,os
m=json.load(open(os.path.expanduser('~/work/runs/gen8-s7-azure1/manifest.json')))
print(json.dumps(dict(spec=m['bots']['8s-32'],systems=m.get('systems'),identity=m['identity'],source_commit=m.get('source_commit')),sort_keys=True))
PY
