# boxctl: timeout=120
# boxctl: timeout=120
# loop session: is BEN in the loop's capsule, and its spec in the lanes' run (read-only).
python3 - <<'PY'
import json, os, glob
H = os.path.expanduser('~')
m = json.load(open(H + '/work/loop/capsule/recovery/manifest.json'))
print('capsule generations:', [g['id'] for g in m['generations']])
print('capsule keys:', sorted(m.keys()))
for g in m['generations']:
    if 'ben' in g['id']: print(json.dumps(g)[:1500])
r = json.load(open(H + '/work/runs/gen8-f-azure3-ben64-1/manifest.json'))
print('lane run generations:', [g['id'] for g in r['generations']], '| roster', r.get('roster'), '| common', r.get('common_bidder'))
for g in r['generations']:
    if 'ben' in g['id']: print(json.dumps(g)[:1500])
print(sorted(os.listdir(H + '/work/runs/gen8-f-azure3-ben64-1'))[:30])
print(sorted(os.listdir(H + '/work/runs/gen8-f-azure3-ben64-1/assets'))[:30])
PY
grep -n "url\|requests\|http" $HOME/work/loop/src/bridge_harness/gen5_arena.py | cut -c1-200 | head -20
ls $HOME/work/loop/capsule/recovery | head -30
