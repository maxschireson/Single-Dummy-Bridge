# boxctl: timeout=240
# Gen 7 phase 1 collector status on this box, one JSON line for pooling; also the finished pre-7 run's totals.
W=$HOME/work; RUN=$W/runs/gen7-phase1-$BOXCTL_BOX
"$W/venv/bin/python" - "$RUN" "$W" <<'PY'
import glob, json, os, subprocess, sys, time
run, w = sys.argv[1:3]
def unit(name):
    return subprocess.run(['systemctl', 'is-active', name], capture_output=True, text=True).stdout.strip()
def summarise(rs):
    out = {}
    for r in rs:
        g = out.setdefault(r['pair'], dict(n=0, sum=0, sumsq=0, won=0, flat=0, lost=0))
        v = r['imps']; g['n'] += 1; g['sum'] += v; g['sumsq'] += v * v
        g['won' if v > 0 else 'lost' if v < 0 else 'flat'] += 1
    return out
now = time.time()
rs = [json.load(open(p)) for p in glob.glob(run + '/receipts/*.json')]
pub = {}
try:
    pub = json.load(open(run + '/publisher-status.json')); pub['age_s'] = round(now - pub.pop('epoch'))
except Exception as e:
    pub = dict(status='unreadable: %r' % e)
m = json.load(open(run + '/manifest.json'))
st = os.statvfs(run)
cache = run + '/dds-cache.sqlite'
out = dict(box=os.environ.get('BOXCTL_BOX'), shard=m.get('shard'), target=m['target'], completed=len(rs), pairs=summarise(rs),
           tables=sum(r['tables'] for r in rs), last_30min=sum(r['completed_epoch'] > now - 1800 for r in rs),
           running_s=round(now - min((r['completed_epoch'] for r in rs), default=now)),
           failures=sorted(os.listdir(run + '/failures')), stop=os.path.exists(run + '/STOP'),
           collector=unit('arena-gen7'), publisher=unit('arena-gen7-publish'), publish=pub,
           disk_free_gb=round(st.f_bavail * st.f_frsize / 1e9, 1), cache_gb=round(os.path.getsize(cache) / 1e9, 2) if os.path.exists(cache) else 0,
           load=[round(x, 1) for x in os.getloadavg()], other_units={u: unit(u) for u in ('pre7-match', 'pre7-publish', 'e2-fetch')})
pre = sorted(glob.glob(w + '/runs/g7s-vs-g6f-01') + glob.glob(w + '/runs/pre7-7s-vs-6f-*'))
if pre:
    prs = [json.load(open(p)) for p in glob.glob(pre[0] + '/receipts/*.json')]
    x = [r['imps'] for r in prs]
    out['pre7'] = dict(run=os.path.basename(pre[0]), n=len(x), sum=sum(x), sumsq=sum(v * v for v in x), won=sum(v > 0 for v in x),
                       flat=sum(v == 0 for v in x), lost=sum(v < 0 for v in x), tables=sum(r['tables'] for r in prs),
                       failures=len(os.listdir(pre[0] + '/failures')))
    log = subprocess.run(['journalctl', '-u', 'pre7-publish', '--no-pager', '-n', '2', '-o', 'cat'], capture_output=True, text=True).stdout.strip().splitlines()
    out['pre7']['publisher_last'] = log[-1][-90:] if log else None
print('P1 ' + json.dumps(out))
PY
