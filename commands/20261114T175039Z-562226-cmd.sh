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
a = rd("$W/runs/bu3-pst200*-[1-8]/results.jsonl"); c = rd("$W/runs/bu4c-pst200*-[1-8]/results.jsonl")
def ms(v):
    m = sum(v)/len(v); return m, (sum((x-m)**2 for x in v)/(len(v)-1)/len(v))**.5
ks = sorted(set(a) & set(c)); k1 = [k for k in ks if k < 512]
print("R4c - R3 paired, first 512: %+.3f +- %.3f (%d); all so far: %+.3f +- %.3f (%d)" % (*ms([c[k]-a[k] for k in k1]), len(k1), *ms([c[k]-a[k] for k in ks]), len(ks)))
print("R4c vs BEN first 512: %+.3f +- %.3f; R3 same deals %+.3f +- %.3f" % (*ms([c[k] for k in k1]), *ms([a[k] for k in k1])))
EOF
for r in bu4c-pst200a bu4c-pst200b bu4c-pst200c; do printf "%s: %s | " $r "$(cat $W/runs/$r-[1-8]/results.jsonl 2>/dev/null | wc -l)"; done; echo; tail -n 1 $W/runs.log | cut -c1-110; date -u +%T
