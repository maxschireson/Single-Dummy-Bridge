# boxctl: timeout=240
# Status of every Gen 8 run on this box (main mix under arena-gen8, BEN lanes under arena-ben@N), one compressed JSON line.
W=$HOME/work
"$W/venv/bin/python" - "$W" <<'PY'
import base64, glob, json, os, re, subprocess, sys, time, zlib
w = sys.argv[1]; box = os.environ.get('BOXCTL_BOX'); now = time.time()
unit = lambda n: subprocess.run(['systemctl', 'is-active', n], capture_output=True, text=True).stdout.strip()
lanes = {}
for n in range(1, 9):
    try:
        for line in open(f'{w}/lanes/{n}.env'):
            if line.startswith('RUN='): lanes[line.strip().split('=', 1)[1]] = n
    except OSError: pass
try: trained = set(json.load(open(w + '/gen8/v41-training-families-union.json')))
except Exception: trained = None
m = re.search(r'--run (\S+)', subprocess.run(['systemctl', 'show', '-p', 'ExecStart', '--value', 'arena-gen8'], capture_output=True, text=True).stdout)
main = m.group(1) if m else None
runs = []
for run in sorted(glob.glob(w + '/runs/gen8-*')):
    if not os.path.exists(run + '/manifest.json'): continue
    name = os.path.basename(run); rs = [json.load(open(p)) for p in glob.glob(run + '/receipts/*.json')]
    pairs = {}
    for r in rs:
        g = pairs.setdefault(r['pair'], dict(n=0, sum=0, sumsq=0, unscored=0)); v = r['imps']
        if v is None: g['unscored'] += 1; continue
        g['n'] += 1; g['sum'] += v; g['sumsq'] += v * v
    try: pub = json.load(open(run + '/publisher-status.json')); pub['age_s'] = round(now - pub.pop('epoch'))
    except Exception: pub = dict(status='none')
    mf = json.load(open(run + '/manifest.json'))
    row = dict(name=name, cohort=mf['identity'][:12], target=mf['target'], completed=len(rs), pairs=pairs,
               excl=(mf.get('evaluation_exclusions') or {}).get('sha256', '')[:12],
               trained_played=(sum(r['family'] in trained for r in rs) if trained is not None else None),
               last_30min=sum(r['completed_epoch'] > now - 1800 for r in rs), failures=sorted(os.listdir(run + '/failures')),
               stop=os.path.exists(run + '/STOP'), publish=dict(status=pub.get('status'), age_s=pub.get('age_s')), commit=(mf.get('source_commit') or '')[:7])
    if run in lanes:
        n = lanes[run]; row.update(kind='lane', lane=n, collector=unit(f'arena-ben@{n}'), publisher=unit(f'arena-ben-publish@{n}'), server=unit(f'ben-server@{n}'))
    elif run == main: row.update(kind='main', collector=unit('arena-gen8'), publisher=unit('arena-gen8-publish'))
    else: row.update(kind='other')
    runs.append(row)
mem = {l.split(':')[0]: int(l.split()[1]) // 1024 for l in open('/proc/meminfo') if l.split(':')[0] in ('MemAvailable',)}
st = os.statvfs(w)
out = dict(box=box, time=now, load=[round(x, 1) for x in os.getloadavg()], mem_gb=round(mem['MemAvailable'] / 1024, 1),
           disk_gb=round(st.f_bavail * st.f_frsize / 1e9, 1), runs=runs, units={u: unit(u) for u in ('gen8-recycle', 'lane-recycle', 'lane-switch', 'go8', 'switch8')})
for key, path, ok in (('recycle8', w + '/gen8/recycle*.log', 'restarting it'), ('lanerecycle', w + '/lanes/recycle.log', 'restarted')):
    try:
        lines = [l for p in glob.glob(path) for l in open(p).read().splitlines() if ok in l or 'left stopped' in l or 'did not stop' in l or 'not restarting' in l]
        out[key] = dict(restarts=sum(ok in l for l in lines), trouble=[l[:150] for l in lines if ok not in l][-2:])
    except Exception: pass
print('BOXZ ' + base64.b64encode(zlib.compress(json.dumps(out, separators=(',', ':')).encode(), 9)).decode())
PY
