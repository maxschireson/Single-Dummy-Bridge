# boxctl: timeout=60
# boxctl: timeout=60
# read-only: counts the 8Z match rows under ~/work/x8 (x8's run); writes nothing
python3 - <<'P'
import json, glob, math, os
fs = sorted(glob.glob(os.path.expanduser('~/work/x8/**/z[12]/results.jsonl'), recursive=True))
print(fs)
R = {}
for f in fs:
    rows = [json.loads(l) for l in open(f) if l.strip()]
    R[f.split('/')[-2]] = {r['index']: r for r in rows}
    x = [r['common'] for r in rows]
    n = len(x); m = sum(x) / n if n else 0
    sd = math.sqrt(sum((v - m) ** 2 for v in x) / max(1, n - 1)) if n > 1 else 0
    print(f.split('/')[-2], 'boards', n, 'IMPs/board %+.3f +- %.3f' % (m, sd / math.sqrt(max(n, 1))))
if 'z1' in R and 'z2' in R:
    k = sorted(set(R['z1']) & set(R['z2']))
    d = [R['z1'][i]['common'] - R['z2'][i]['common'] for i in k]
    n = len(d); m = sum(d) / n
    sd = math.sqrt(sum((v - m) ** 2 for v in d) / max(1, n - 1))
    print('z1 - z2 paired on', n, 'deals: %+.3f +- %.3f IMPs/board' % (m, sd / math.sqrt(n)))
P
