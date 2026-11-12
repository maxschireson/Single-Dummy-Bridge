# boxctl: timeout=150
L=$HOME/work/lanes; W=$HOME/work
. $L/role.env
echo "== $(date -u +%T) $BOX $LABEL; ben-lanes $(systemctl is-active ben-lanes); g8-queue $(systemctl is-active g8-queue 2>/dev/null); g8-publish $(systemctl is-active g8-publish 2>/dev/null)"
bash $L/lane.sh status 2>&1 | cut -c1-330
echo "== cohorts"
$W/venv/bin/python - "$W" "$BOX" "$LABEL" <<'PY'
import glob, gzip, json, os, sys, time, collections
w, box, label = sys.argv[1:4]
now = time.time()
allr = []
for lane in range(1, 9):
    p = f'{w}/lanes/{lane}.prepare.json'
    if not os.path.exists(p): print('lane', lane, 'no prepare record'); continue
    d = json.load(open(p))
    run = f'{w}/runs/gen7-phase1-{box}-{label}-{lane}'
    man = json.load(open(run + '/manifest.json')) if os.path.exists(run + '/manifest.json') else {}
    rs = [json.load(open(q)) for q in glob.glob(run + '/receipts/*.json')]
    allr += rs
    first = min((r['completed_epoch'] for r in rs), default=None)
    print(f"lane {lane}: cohort {d['identity'][:12]} shard {d['shard']['index']}/{d['shard']['of']} target {d['target']} boards {len(rs)} first board {time.strftime('%H:%M:%S', time.gmtime(first)) if first else None} manifest keys {sorted(man)[:0]}")
ts = sorted(r['completed_epoch'] for r in allr)
for m in (10, 5):
    n = sum(t > now - 60 * m for t in ts)
    print(f"all lanes: {n} boards in the last {m} min = {n * 60 / m:.0f}/h")
secs = [r.get('seconds') for r in allr if r.get('seconds') is not None]
if secs: print('board seconds: median', sorted(secs)[len(secs) // 2], 'n', len(secs))
print('receipt keys:', sorted(allr[0]) if allr else None)
# one episode: where BEN's sample count shows
eps = sorted(glob.glob(f'{w}/runs/gen7-phase1-{box}-{label}-1/episodes/*.json.gz'))
if eps:
    d = json.load(gzip.open(eps[-1], 'rt'))
    print('episode keys:', sorted(d)[:30])
    def walk(o, path, out, depth=0):
        if depth > 7: return
        if isinstance(o, dict):
            for k, v in o.items():
                if 'sampl' in k.lower() or 'ben' in k.lower():
                    out[path + '/' + k].append(v if not isinstance(v, (dict, list)) else type(v).__name__)
                walk(v, path + '/' + k, out, depth + 1)
        elif isinstance(o, list):
            for v in o[:400]: walk(v, path + '[]', out, depth + 1)
    out = collections.defaultdict(list); walk(d, '', out)
    for k, v in list(out.items())[:25]:
        c = collections.Counter(map(str, v)).most_common(6)
        print('  ', k[-110:], c)
PY
echo "== last orchestrate lines"; tail -5 $L/orchestrate.log | cut -c1-220
echo "== ben server log, lane 1 (sample lines)"; grep -i -E "sample" $L/1.ben.log | tail -4 | cut -c1-220
echo "== cpu"; top -bn1 | head -4 | tail -2 | cut -c1-120; ps -eo pcpu,comm --sort=-pcpu | head -6
