W=$HOME/work/loop; f=$W/runs/h4c-pst/results.jsonl; python3 -c "
import json
v=[]
for l in open(\"$f\"):
    try: v.append(json.loads(l)[\"common\"])
    except Exception: pass
n=len(v); m=sum(v)/n; se=(sum((x-m)**2 for x in v)/(n-1)/n)**.5
print(\"h4c-pst %+.3f +- %.3f (%d)\" % (m, se, n))" 2>&1 | tail -1; tail -n 3 $W/runs.log | cut -c1-140; systemctl list-units --plain --no-legend "loop-*" | awk "{print \$1, \$4}"; date -u +%T
