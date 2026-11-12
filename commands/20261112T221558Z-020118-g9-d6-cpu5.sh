# boxctl: timeout=120
cd ~/work/g9/runs/d6-arrival/control/results 2>/dev/null || exit 1
python3 - <<'PY'
import json, glob, collections
for f in sorted(glob.glob('e*/slot0.jsonl')):
    rows=[json.loads(l) for l in open(f) if l.strip()]
    by=collections.defaultdict(list)
    for r in rows: by[(r['pair'], r.get('floor') is not None)].append(r.get('cpu') or 0)
    print(f, len(rows), 'boards')
    for (p,fl),c in sorted(by.items()): print('   %-22s floor=%-5s n=%4d cpu/board %.1f' % (p, fl, len(c), sum(c)/len(c)))
PY
uptime; free -g | head -2
