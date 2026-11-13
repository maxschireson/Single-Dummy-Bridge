# boxctl: timeout=200
W=$HOME/work/x8; PY=$HOME/work/venv/bin/python; $PY - <<"P"
import json, math, os
W = os.environ["HOME"] + "/work/x8/runs/"
def rows(z): return [json.loads(l) for l in open(W + z + "/results.jsonl")]
def ms(v):
    n = len(v); m = sum(v)/n; return n, m, math.sqrt(sum((x-m)**2 for x in v)/(n-1)/n)
R = {z: rows(z) for z in ("z3", "z5", "x5", "x4", "x3")}
for z, r in R.items():
    n, m, s = ms([x["common"] for x in r]); cpu = sum(x["cpu"] for x in r)/n
    print(z, n, "%+.3f +- %.3f cpu %.1f" % (m, s, cpu))
idx = {z: {x["index"]: x["common"] for x in r} for z, r in R.items()}
for a, b in (("z3","z5"), ("x5","z3"), ("x5","z5"), ("x4","z3")):
    c = sorted(set(idx[a]) & set(idx[b])); n, m, s = ms([idx[a][k]-idx[b][k] for k in c]); print(a, "-", b, "paired", n, "%+.3f +- %.3f" % (m, s))
P
grep -A8 "with rollout\|with guarantee\|with odds" /tmp/f5.txt | head -30; tail -2 /tmp/f5.txt
