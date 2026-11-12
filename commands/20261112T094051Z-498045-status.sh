# boxctl: timeout=240
# Status of every Gen 7 and Gen 7.1 run on this box, one JSON line.
W=$HOME/work
"$W/venv/bin/python" - "$W" <<'PY'
import glob, json, os, re, subprocess, sys, time
w = sys.argv[1]; box = os.environ.get('BOXCTL_BOX'); now = time.time()
def unit(name):
    return subprocess.run(['systemctl', 'is-active', name], capture_output=True, text=True).stdout.strip()
current = {}            # lane number -> the run folder its units point at
for n in range(1, 9):
    try:
        for line in open(f'{w}/lanes/{n}.env'):
            if line.startswith('RUN='): current[n] = line.strip().split('=', 1)[1]
    except OSError:
        pass
try: trained = set(json.load(open(w + '/gen71/all-training-families.json')))        # families the policy net v4.1 was trained on
except Exception: trained = None
current71 = None        # the run the unit arena-gen71 points at
try:
    m71 = re.search(r'--run (\S+)', subprocess.run(['systemctl', 'show', '-p', 'ExecStart', '--value', 'arena-gen71'], capture_output=True, text=True).stdout)
    current71 = m71.group(1) if m71 else None
except Exception:
    pass
runs = []
for run in sorted(glob.glob(w + '/runs/gen7-phase1-*') + glob.glob(w + '/runs/gen71-*') + glob.glob(w + '/runs/gen71fresh-*')):
    if not os.path.isdir(run) or not os.path.exists(run + '/manifest.json'): continue
    name = os.path.basename(run); lane = None; ben = None; gen = '7.1' if name.startswith('gen71') else '7.0'
    m = re.match(r'(gen7-phase1|gen71|gen71fresh)-[a-z0-9]+-(ben16|ben64)-(\d+)$', name)
    if m: kind, ben, lane = 'lane', m.group(2), int(m.group(3))
    elif name.startswith('gen71-') and run == current71: kind = 'gen71'
    elif name.startswith('gen71-'): kind = 'gen71-first'
    elif name == f'gen7-phase1-selfplay-capture-{box}': kind = 'selfplay'
    elif name == f'gen7-phase1-selfplay-{box}': kind = 'selfplay-trial'
    else: kind = 'nonben'
    rs = [json.load(open(p)) for p in glob.glob(run + '/receipts/*.json')]
    pairs = {}; pairs_fresh = {}
    for r in rs:
        for table in ((pairs, pairs_fresh) if trained is not None and r['family'] not in trained else (pairs,)):
            g = table.setdefault(r['pair'], dict(n=0, sum=0, sumsq=0, won=0, flat=0, lost=0, unscored=0))
            v = r['imps']
            if v is None: g['unscored'] += 1; continue            # self-play: a board with no IMP comparison
            g['n'] += 1; g['sum'] += v; g['sumsq'] += v * v; g['won' if v > 0 else 'lost' if v < 0 else 'flat'] += 1
    try:
        pub = json.load(open(run + '/publisher-status.json')); pub['age_s'] = round(now - pub.pop('epoch'))
    except Exception:
        pub = dict(status='none')
    mf = json.load(open(run + '/manifest.json'))
    row = dict(name=name, kind=kind, gen=gen, ben=ben, lane=lane, cohort=mf['identity'][:12], shard=mf.get('shard'), target=mf['target'], completed=len(rs), pairs=pairs, pairs_fresh=(pairs_fresh if trained is not None else None), excludes=bool(mf.get('evaluation_exclusions')),
               last_30min=sum(r['completed_epoch'] > now - 1800 for r in rs), last_10min=sum(r['completed_epoch'] > now - 600 for r in rs),
               last_epoch=max((r['completed_epoch'] for r in rs), default=None),
               failures=sorted(os.listdir(run + '/failures')), stop=os.path.exists(run + '/STOP'), publish=pub, source_commit=(mf.get('source_commit') or '')[:7])
    if kind == 'lane':
        row['current'] = current.get(lane) == run
        if row['current']: row.update(collector=unit(f'arena-ben@{lane}'), publisher=unit(f'arena-ben-publish@{lane}'), server=unit(f'ben-server@{lane}'))
        else: row.update(collector='finished', publisher='finished', server='n/a')
    elif kind == 'nonben': row.update(collector=unit('arena-gen7'), publisher=unit('arena-gen7-publish'))
    elif kind == 'selfplay': row.update(collector=unit('arena-selfplay'), publisher=unit('arena-selfplay-publish'))
    elif kind == 'gen71': row.update(collector=unit('arena-gen71'), publisher=unit('arena-gen71-publish'))
    else: row.update(collector='finished', publisher='finished')
    runs.append(row)
st = os.statvfs(w)
mem = {l.split(':')[0]: int(l.split()[1]) // 1024 for l in open('/proc/meminfo') if l.split(':')[0] in ('MemTotal', 'MemAvailable')}
out = dict(box=box, time=now, load=[round(x, 1) for x in os.getloadavg()], mem_available_gb=round(mem['MemAvailable'] / 1024, 1),
           disk_free_gb=round(st.f_bavail * st.f_frsize / 1e9, 1), runs=runs,
           other_units={u: unit(u) for u in ('lane-recycle', 'gen71-recycle', 'switch71', 'go71b')})
try:
    lines = [l for l in open(w + '/lanes/recycle.log').read().strip().splitlines() if 'restarted' in l or 'left stopped' in l or 'did not stop' in l]
    out['recycle'] = dict(restarts=sum('restarted' in l for l in lines), trouble=[l[:160] for l in lines if 'restarted' not in l][-3:], last=lines[-1][:120] if lines else None)
except Exception:
    pass
try:
    lines = [l for l in open(w + '/gen71/recycle71.log').read().strip().splitlines() if 'restarted with' in l or 'left stopped' in l or 'did not stop' in l or 'not restarting' in l]
    out['recycle71'] = dict(restarts=sum('restarted with' in l for l in lines), trouble=[l[:160] for l in lines if 'restarted with' not in l][-3:], last=lines[-1][:120] if lines else None)
except Exception:
    pass
try:
    pid = subprocess.run(['systemctl', 'show', '-p', 'MainPID', '--value', 'arena-gen71'], capture_output=True, text=True).stdout.strip()
    if pid and pid != '0':
        rss = subprocess.run(['ps', '-o', 'rss=', '--pid', pid, '--ppid', pid], capture_output=True, text=True).stdout.split()
        out['gen71_tree_gb'] = round(sum(int(x) for x in rss) / 1048576, 1)
except Exception:
    pass
import base64, zlib
print('BOXZ ' + base64.b64encode(zlib.compress(json.dumps(out, separators=(',', ':')).encode(), 9)).decode())
PY
