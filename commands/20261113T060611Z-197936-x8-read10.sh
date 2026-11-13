# boxctl: timeout=200
W=$HOME/work/x8; PY=$HOME/work/venv/bin/python; $PY - <<"P"
import json, math, os
W = os.environ["HOME"] + "/work/x8/runs/"
def ms(v):
    n = len(v); m = sum(v)/n; return n, m, (math.sqrt(sum((x-m)**2 for x in v)/(n-1)/n) if n > 1 else 0)
idx = {}
for z in ("x1", "x3", "x4", "x5", "x6", "z3", "z5"):
    r = [json.loads(l) for l in open(W + z + "/results.jsonl")]
    idx[z] = {x["index"]: x["common"] for x in r}
    n, m, s = ms(list(idx[z].values())); cpu = sum(x["cpu"] for x in r)/len(r)
    print(z, n, "%+.3f +- %.3f cpu %.1f" % (m, s, cpu), "max index", max(idx[z]))
for a, b in (("x4","x5"), ("x1","x5"), ("x3","x5"), ("x6","x5"), ("x1","x4"), ("x3","x4"), ("x6","x4"), ("x5","z3")):
    c = sorted(set(idx[a]) & set(idx[b]))
    if len(c) < 2: continue
    n, m, s = ms([idx[a][k]-idx[b][k] for k in c]); ma = sum(idx[a][k] for k in c)/n; mb = sum(idx[b][k] for k in c)/n
    print(a, "-", b, "paired", n, "%+.3f +- %.3f  (%s %+.3f, %s %+.3f)" % (m, s, a, ma, b, mb))
P
