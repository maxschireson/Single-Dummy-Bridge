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
ks = sorted(set(a) & set(c))
print("R4c vs BEN %+.3f +- %.3f (%d); R3 same deals %+.3f +- %.3f; R4c - R3 paired %+.3f +- %.3f" % (*ms([c[k] for k in ks]), len(ks), *ms([a[k] for k in ks]), *ms([c[k]-a[k] for k in ks])))
ks2 = sorted(set(b) & set(c)); print("R4 - R4c paired %+.3f +- %.3f (%d)" % (*ms([b[k]-c[k] for k in ks2]), len(ks2)))
d = [c[k]-a[k] for k in ks]; big = [x for x in d if abs(x) >= 10]
print("R4c - R3 swings of 10+: %d for R4c (%+d), %d against (%+d); under 10: %+d" % (sum(1 for x in big if x > 0), sum(x for x in big if x > 0), sum(1 for x in big if x < 0), sum(x for x in big if x < 0), sum(x for x in d if abs(x) < 10)))
EOF
for r in bu4c-pst200a bu4c-pst200b; do printf "%s: %s | " $r "$(cat $W/runs/$r-[1-8]/results.jsonl 2>/dev/null | wc -l)"; done; echo; tail -n 1 $W/runs.log | cut -c1-120; date -u +%T
