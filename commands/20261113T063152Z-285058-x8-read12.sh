# boxctl: timeout=200
W=$HOME/work/x8; PY=$HOME/work/venv/bin/python; $PY - <<"P"
import json, math, os
W = os.environ["HOME"] + "/work/x8/runs/"
def ms(v):
    n = len(v); m = sum(v)/n; return n, m, (math.sqrt(sum((x-m)**2 for x in v)/(n-1)/n) if n > 1 else 0)
idx = {}
for z in ("x1", "x4", "x5", "x6"):
    r = [json.loads(l) for l in open(W + z + "/results.jsonl")]
    idx[z] = {x["index"]: x["common"] for x in r}
    n, m, s = ms(list(idx[z].values())); cpu = sum(x["cpu"] for x in r)/len(r)
    print(z, n, "%+.3f +- %.3f cpu %.1f" % (m, s, cpu))
for a, b in (("x4","x5"), ("x6","x5"), ("x4","x6"), ("x4","x1"), ("x6","x1")):
    c = sorted(set(idx[a]) & set(idx[b]))
    n, m, s = ms([idx[a][k]-idx[b][k] for k in c])
    print(a, "-", b, "paired", n, "%+.3f +- %.3f" % (m, s))
P
for z in x4 x6; do echo "== $z"; $PY $W/bin/x8_forks.py $W/runs/$z > /tmp/f_$z.txt 2>&1; sed -n 1,2p /tmp/f_$z.txt; grep -A2 "^  with mix\|^  with blend\|^  with guarantee" /tmp/f_$z.txt; done
