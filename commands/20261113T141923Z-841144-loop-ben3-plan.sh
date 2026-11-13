# boxctl: timeout=120
# boxctl: timeout=120
# loop session: the BEN bot's spec in the lanes' plan (read-only).
python3 - <<'PY'
import json, os, glob
p = json.load(open(os.path.expanduser('~/work/lanes/plan-ben64.json')))
print('keys', list(p.keys()))
def walk(x, path=''):
    if isinstance(x, dict):
        if any('ben' in str(v).lower() for v in (x.get('id'), x.get('engine'), x.get('url'))) or 'url' in x:
            print(path, json.dumps(x)[:1200]); return
        for k, v in x.items(): walk(v, path + '/' + str(k))
    elif isinstance(x, list):
        for i, v in enumerate(x): walk(v, path + f'[{i}]')
walk(p)
print({k: (v if not isinstance(v, (dict, list)) else type(v).__name__) for k, v in p.items()})
PY
sed -n '/arena-ben@.service/,/^UNIT/p' $HOME/work/lanes/lane.sh | cut -c1-260 | head -30
cat /etc/systemd/system/arena-ben@.service | cut -c1-260
