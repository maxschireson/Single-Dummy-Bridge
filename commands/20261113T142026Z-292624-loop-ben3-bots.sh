# boxctl: timeout=120
# boxctl: timeout=120
# loop session: BEN's spec in the loop's capsule and in the lanes' run (read-only).
python3 - <<'PY'
import json, os
H = os.path.expanduser('~')
m = json.load(open(H + '/work/loop/capsule/recovery/manifest.json'))
print('capsule bots:', sorted(m['bots']))
for k, g in m['bots'].items():
    if 'ben' in k: print(k, json.dumps(g)[:700])
r = json.load(open(H + '/work/runs/gen8-f-azure3-ben64-1/manifest.json'))
print('lane run bots:', sorted(r['bots']), '| roster', r.get('roster'), '| schedule', r.get('pair_schedule'))
for k, g in r['bots'].items():
    if 'ben' in k: print(k, json.dumps(g)[:1200])
PY
grep -rn "def player_factory" $HOME/work/loop/src/bridge_harness/*.py | cut -c1-160
for i in 1 2 3; do cat $HOME/work/lanes/$i.env | grep -n "BEN_PORT\|BEN_CONF" | cut -c1-140; done
ip netns list 2>/dev/null | head -10
