# boxctl: timeout=60
# boxctl: timeout=60
W=$HOME/work/loop
python3 - <<'PY'
import json, os
m = json.load(open(os.path.expanduser('~/work/loop/capsule/recovery/manifest.json')))
b = m['bots']
print('common bidder', m.get('common_bidder'), '| bots', len(b))
for k, v in b.items():
    print(k, '|', v.get('engine') or v.get('kind') or '?', '|', (v.get('label') or v.get('name') or '')[:70], '|', sorted(v)[:8])
PY
