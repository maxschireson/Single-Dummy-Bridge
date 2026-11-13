# boxctl: timeout=120
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
for a, b in (("x4","x5"), ("x6","x5"), ("x4","x6")):
    c = sorted(set(idx[a]) & set(idx[b])); n, m, s = ms([idx[a][k]-idx[b][k] for k in c])
    print(a, "-", b, "paired", n, "%+.3f +- %.3f" % (m, s))
P
head -1 /tmp/f_x6.txt; head -1 /tmp/f_x4.txt
