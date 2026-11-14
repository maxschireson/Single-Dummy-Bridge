W=$HOME/work/loop; python3 - <<EOF
import json, glob
def rd(p):
    d = {}
    for f in glob.glob(p):
        for l in open(f):
            try:
                r = json.loads(l); d[r["index"]] = r["common"]
            except Exception: pass
    return d
a = rd("$W/runs/bu3-pst200*-[1-8]/results.jsonl"); b = rd("$W/runs/bu4-pst200*-[1-8]/results.jsonl"); c = rd("$W/runs/bu4c-pst200*-[1-8]/results.jsonl")
def ms(v):
    m = sum(v)/len(v); return m, (sum((x-m)**2 for x in v)/(len(v)-1)/len(v))**.5
for name, x in (("R4", b), ("R4c", c)):
    ks = sorted(set(a) & set(x))
    if len(ks) > 2:
        print("%s vs BEN %+.3f +- %.3f (%d); R3 same deals %+.3f +- %.3f; %s - R3 paired %+.3f +- %.3f" % (name, *ms([x[k] for k in ks]), len(ks), *ms([a[k] for k in ks]), name, *ms([x[k]-a[k] for k in ks])))
ks = sorted(set(b) & set(c))
if len(ks) > 2: print("R4 - R4c paired %+.3f +- %.3f (%d)" % (*ms([b[k]-c[k] for k in ks]), len(ks)))
EOF
date -u +%T
