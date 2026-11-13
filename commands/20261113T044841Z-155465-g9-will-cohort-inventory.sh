# boxctl: timeout=300
#!/bin/bash
# Read-only inventory of azure4 for dave's cohort preflight (G9 cohort, 13 Nov): candidate source runs,
# BEN servers, the v4.1 families list. Writes nothing.
set -u
echo "== host $(hostname) $(date -u +%FT%TZ) load $(cut -d' ' -f1-3 /proc/loadavg) nproc $(nproc)"
python3 - <<'PY'
import json, os, glob, collections
roots = [os.path.expanduser('~'), '/srv', '/data', '/mnt', '/opt']
runs = []
for top in roots:
    if not os.path.isdir(top):
        continue
    for d, subs, files in os.walk(top):
        depth = d[len(top):].count(os.sep)
        subs[:] = [s for s in subs if s not in ('episodes', 'receipts', 'failures', 'artifacts', 'assets', '.git', 'node_modules', '.cache', 'venv', '.venv', 'site-packages', 'proc')] if depth < 7 else []
        if 'manifest.json' in files and ('state.json' in files or 'receipts' in subs or os.path.isdir(os.path.join(d, 'receipts'))):
            runs.append(d)
seen = set(); out = []
for d in sorted(runs):
    real = os.path.realpath(d)
    if real in seen: continue
    seen.add(real)
    try:
        m = json.load(open(os.path.join(d, 'manifest.json')))
    except Exception as e:
        out.append(dict(path=d, error=str(e)[:80])); continue
    if not isinstance(m, dict) or 'target' not in m:
        continue
    def count(sub, pat):
        try: return len(glob.glob(os.path.join(d, sub, pat)))
        except Exception: return None
    idx = None
    if m.get('source_indices') and os.path.exists(os.path.join(d, m['source_indices'])):
        try: idx = json.load(open(os.path.join(d, m['source_indices'])))
        except Exception: idx = None
    out.append(dict(path=d, identity=str(m.get('identity'))[:16], campaign=m.get('campaign'), target=m.get('target'),
        receipts=count('receipts', '*.json'), episodes=count('episodes', '*.json.gz'), failures=count('failures', '*.json'),
        STOP=os.path.exists(os.path.join(d, 'STOP')), WATCHDOG_STOP=os.path.exists(os.path.join(d, 'WATCHDOG_STOP')),
        source_generation=str(m.get('source_generation') or '')[:16], shard=m.get('shard'), n_source_indices=len(idx) if idx is not None else None,
        corpus=m.get('corpus'), mtime_receipts=max([os.path.getmtime(p) for p in glob.glob(os.path.join(d, 'receipts', '*.json'))[-50:]] or [0]),
        owner_hint=d.split(os.sep)[3] if len(d.split(os.sep)) > 3 else ''))
import time
for r in out:
    if 'mtime_receipts' in r and r['mtime_receipts']:
        r['last_receipt_utc'] = time.strftime('%m-%d %H:%M', time.gmtime(r.pop('mtime_receipts')))
    else:
        r.pop('mtime_receipts', None)
    print(json.dumps(r))
# allocation of each source's deals to derived runs on this box
by_source = collections.defaultdict(list)
for r in out:
    if r.get('source_generation'): by_source[r['source_generation']].append(r['path'])
print('== derived runs by source identity prefix:', json.dumps(by_source))
PY
echo "== BEN"
systemctl list-units --all --no-pager --plain 2>/dev/null | grep -i ben | head -20
(ss -ltnp 2>/dev/null || netstat -ltnp 2>/dev/null) | grep -E ':(808[0-9]|809[0-9]|5000|5001)\b' | head
ls -d ~/ben* ~/BEN* ~/work/ben* /opt/ben* 2>/dev/null | head
pgrep -af -i 'gameserver|ben.*\.conf|appserver|ben/src' | head -5
command -v docker >/dev/null && docker ps --format '{{.Names}} {{.Image}}' 2>/dev/null | head
echo "== families list"
find ~ /srv /data /mnt -maxdepth 7 -name 'v41-training-families-union*.json' 2>/dev/null | head
echo "== g9 units"
systemctl list-units --no-pager --plain 'g9-*' 'g8-*' 2>/dev/null | grep -E '^(g9|g8)-' | head -20
df -h ~ | tail -1
