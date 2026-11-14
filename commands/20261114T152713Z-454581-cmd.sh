W=$HOME/work/loop; python3 - <<EOF
import json, glob
def rd(p):
    d = {}
    for f in glob.glob(p):
        for l in open(f):
            if l.strip():
                r = json.loads(l); d[r["index"]] = r["common"]
    return d
a = rd("$W/runs/bu3-pst200*-[1-8]/results.jsonl"); b = rd("$W/runs/bu4-pst200*-[1-8]/results.jsonl")
ks = sorted(set(a) & set(b)); n = len(ks)
def ms(v):
    m = sum(v)/len(v); return m, (sum((x-m)**2 for x in v)/(len(v)-1)/len(v))**.5
print("R4 vs BEN %+.3f +- %.3f (%d); R3 same deals %+.3f +- %.3f; R4 - R3 paired %+.3f +- %.3f" % (*ms([b[k] for k in ks]), n, *ms([a[k] for k in ks]), *ms([b[k]-a[k] for k in ks])))
EOF
