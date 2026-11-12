# boxctl: timeout=240
# Status of every Gen 7 phase 1 run on this box (the non-BEN cohort and any BEN lanes), one JSON line.
W=$HOME/work
"$W/venv/bin/python" - "$W" <<'PY'
import glob, json, os, re, subprocess, sys, time
w = sys.argv[1]; box = os.environ.get('BOXCTL_BOX'); now = time.time()
def unit(name):
    return subprocess.run(['systemctl', 'is-active', name], capture_output=True, text=True).stdout.strip()
runs = []
for run in sorted(glob.glob(w + '/runs/gen7-phase1-*')):
    if not os.path.isdir(run) or not os.path.exists(run + '/manifest.json'): continue
    name = os.path.basename(run); m = re.match(r'gen7-phase1-[a-z0-9]+-(ben16|ben64)-(\d+)$', name)
    kind, lane = (m.group(1), int(m.group(2))) if m else ('nonben', None)
    if name == f'gen7-phase1-selfplay-capture-{box}': kind = 'selfplay'
    elif name == f'gen7-phase1-selfplay-{box}': kind = 'selfplay-trial'
    rs = [json.load(open(p)) for p in glob.glob(run + '/receipts/*.json')]
    pairs = {}
    for r in rs:
        g = pairs.setdefault(r['pair'], dict(n=0, sum=0, sumsq=0, won=0, flat=0, lost=0, unscored=0))
        v = r['imps']
        if v is None: g['unscored'] += 1; continue            # self-play: a board with no IMP comparison
        g['n'] += 1; g['sum'] += v; g['sumsq'] += v * v; g['won' if v > 0 else 'lost' if v < 0 else 'flat'] += 1
    try:
        pub = json.load(open(run + '/publisher-status.json')); pub['age_s'] = round(now - pub.pop('epoch'))
    except Exception:
        pub = dict(status='none')
    mf = json.load(open(run + '/manifest.json'))
    cache = run + '/dds-cache.sqlite'
    row = dict(name=name, kind=kind, lane=lane, cohort=mf['identity'][:12], shard=mf.get('shard'), target=mf['target'], completed=len(rs), pairs=pairs,
               last_30min=sum(r['completed_epoch'] > now - 1800 for r in rs), last_10min=sum(r['completed_epoch'] > now - 600 for r in rs),
               first_epoch=min((r['completed_epoch'] for r in rs), default=None), last_epoch=max((r['completed_epoch'] for r in rs), default=None),
               failures=sorted(os.listdir(run + '/failures')), stop=os.path.exists(run + '/STOP'), publish=pub,
               cache_gb=round(os.path.getsize(cache) / 1e9, 2) if os.path.exists(cache) else 0)
    if kind == 'nonben':
        row.update(collector=unit('arena-gen7'), publisher=unit('arena-gen7-publish'))
    elif kind == 'selfplay':
        row.update(collector=unit('arena-selfplay'), publisher=unit('arena-selfplay-publish'), source_commit=mf.get('source_commit', '')[:7])
    elif kind == 'selfplay-trial':
        row.update(collector='finished', publisher='finished', source_commit=mf.get('source_commit', '')[:7])
    else:
        row.update(collector=unit(f'arena-ben@{lane}'), publisher=unit(f'arena-ben-publish@{lane}'), server=unit(f'ben-server@{lane}'))
    runs.append(row)
st = os.statvfs(w)
mem = {l.split(':')[0]: int(l.split()[1]) // 1024 for l in open('/proc/meminfo') if l.split(':')[0] in ('MemTotal', 'MemAvailable')}
out = dict(box=box, time=now, load=[round(x, 1) for x in os.getloadavg()], mem_available_gb=round(mem['MemAvailable'] / 1024, 1),
           disk_free_gb=round(st.f_bavail * st.f_frsize / 1e9, 1), runs=runs,
           other_units={u: unit(u) for u in ('lane-recycle',)})
try:
    lines = [l for l in open(w + '/lanes/recycle.log').read().strip().splitlines() if 'restarted' in l or 'left stopped' in l or 'did not stop' in l]
    out['recycle'] = dict(restarts=sum('restarted' in l for l in lines), trouble=[l[:160] for l in lines if 'restarted' not in l][-3:], last=lines[-1][:120] if lines else None)
except Exception:
    pass
print('BOX ' + json.dumps(out))
PY
