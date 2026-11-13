# boxctl: timeout=120
W=$HOME/work/x8; PY=$HOME/work/venv/bin/python; for z in z3 z4 z5 x3; do $PY - $W/runs/$z <<"P"
import json, math, sys
rows = [json.loads(l) for l in open(sys.argv[1] + "/results.jsonl")]
v = [r["common"] for r in rows]; n = len(v); m = sum(v)/n; s = math.sqrt(sum((x-m)**2 for x in v)/(n-1)/n)
print(sys.argv[1].split("/")[-1], n, f"{m:+.3f} +- {s:.3f}", "cpu", round(sum(r["cpu"] for r in rows)/n, 1))
P
done; $PY - <<"P"
import json, math, os
W = os.environ["HOME"] + "/work/x8/runs/"
def load(z): return {json.loads(l)["index"]: json.loads(l)["common"] for l in open(W + z + "/results.jsonl")}
for a, b in (("z3", "z5"), ("x3", "z3")):
    A, B = load(a), load(b); c = sorted(set(A) & set(B)); x = [A[k]-B[k] for k in c]; n = len(x); m = sum(x)/n
    s = math.sqrt(sum((v-m)**2 for v in x)/(n-1)/n); print(f"{a}-{b} paired on {n}: {m:+.3f} +- {s:.3f}")
P
