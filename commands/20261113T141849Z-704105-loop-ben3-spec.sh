# boxctl: timeout=120
# boxctl: timeout=120
# loop session: the BEN bot's spec and how a lane's collector reaches its server (read-only).
W=$HOME/work; L=$W/lanes
python3 - <<'PY'
import json, os
p = json.load(open(os.path.expanduser('~/work/lanes/plan-ben64.json')))
print(list(p.keys()))
for k in ('roster', 'pairs', 'common_bidder', 'bots', 'generations'):
    v = p.get(k)
    if isinstance(v, dict):
        for name, spec in v.items():
            if 'ben' in name: print(k, name, json.dumps(spec)[:900])
    elif isinstance(v, list):
        for spec in v:
            if isinstance(spec, dict) and 'ben' in str(spec.get('id', '')): print(k, json.dumps(spec)[:900])
            elif not isinstance(spec, dict): print(k, str(spec)[:200])
    elif v is not None: print(k, str(v)[:200])
PY
sed -n 43,75p "$L/lane.sh" | cut -c1-230
grep -n "netns\|NetworkNamespace\|BEN_PORT\|BEN_CONF\|collector\|gen7_alpha\|ExecStart" "$L/lane.sh" | cut -c1-220 | head -30
cat /etc/systemd/system/ben-server@.service 2>/dev/null | cut -c1-200; ls /etc/systemd/system | grep -i "lane\|ben" | head; cat "$L"/1.env 2>/dev/null | head -8; ls "$L" | grep -v cache | head -40
systemctl is-active ben-server@1 ben-server@8 | tr '\n' ' '; ps -eo pid,pcpu,rss,etimes,cmd | grep gameapi | grep -v grep | cut -c1-150 | head -9
