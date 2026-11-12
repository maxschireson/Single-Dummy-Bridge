# boxctl: timeout=180
# Pre-7 match progress on this box, one JSON line for pooling plus unit states.
RUN=$(ls -d $HOME/work/runs/g7s-vs-g6f-01 $HOME/work/runs/pre7-7s-vs-6f-* 2>/dev/null | head -1)
echo "units: match $(systemctl is-active pre7-match), publish $(systemctl is-active pre7-publish); $(uptime | sed 's/.*load/load/')"
journalctl -u pre7-publish --no-pager -n 1 -o cat | cut -c1-120
"$HOME/work/venv/bin/python" - "$RUN" <<'PY'
import glob, json, os, sys, time
run = sys.argv[1]
rs = sorted((json.load(open(p)) for p in glob.glob(run + '/receipts/*.json')), key=lambda r: r['completed_epoch'])
x = [r['imps'] for r in rs]
now = time.time()
recent = [r for r in rs if r['completed_epoch'] > now - 1800]
out = dict(box=os.environ.get('BOXCTL_BOX'), run=os.path.basename(run), n=len(x), sum=sum(x), sumsq=sum(v * v for v in x),
           won=sum(v > 0 for v in x), flat=sum(v == 0 for v in x), lost=sum(v < 0 for v in x),
           tables=sum(r['tables'] for r in rs), last_30min=len(recent),
           rate_30min=round(len(recent) * 2) if rs and now - rs[0]['completed_epoch'] > 1800 else None,
           failures=len(os.listdir(run + '/failures')), stop=os.path.exists(run + '/STOP'),
           disk_free_gb=round(os.statvfs(run).f_bavail * os.statvfs(run).f_frsize / 1e9, 1))
print('PRE7 ' + json.dumps(out))
PY
