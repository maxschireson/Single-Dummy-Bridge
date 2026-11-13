# boxctl: timeout=200
W=$HOME/work/x8; PY=$HOME/work/venv/bin/python; $PY - <<"P"
import json, math, os
W = os.environ["HOME"] + "/work/x8/runs/"
def rows(z): return [json.loads(l) for l in open(W + z + "/results.jsonl")]
def ms(v):
    n = len(v); m = sum(v)/n; return n, m, math.sqrt(sum((x-m)**2 for x in v)/(n-1)/n)
R = {z: rows(z) for z in ("z3", "z5", "x5", "x4", "x3")}
for z, r in R.items():
    n, m, s = ms([x["common"] for x in r]); print(f"{z} {n} {m:+.3f} +- {s:.3f} cpu {sum(x[\"cpu\"] for x in r)/n:.1f}")
idx = {z: {x["index"]: x["common"] for x in r} for z, r in R.items()}
for a, b in (("z3","z5"), ("x5","z3"), ("x5","z5"), ("x4","z3")):
    c = sorted(set(idx[a]) & set(idx[b])); n, m, s = ms([idx[a][k]-idx[b][k] for k in c]); print(f"{a}-{b} paired {n}: {m:+.3f} +- {s:.3f}")
P
$PY $W/bin/x8_forks.py $W/runs/x5 > /tmp/f5.txt 2>&1; head -18 /tmp/f5.txt; grep -A6 "with mix\|with claim\|with rollout" /tmp/f5.txt | grep -v "trick [0-9]" | head -40
