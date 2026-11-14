W=$HOME/work/loop; f=$W/runs/h4c-pst/results.jsonl; python3 -c "
import json
v=[json.loads(l)[\"common\"] for l in open(\"$f\") if l.strip()]
n=len(v); m=sum(v)/n; se=(sum((x-m)**2 for x in v)/(n-1)/n)**.5
print(\"h4c-pst %+.3f +- %.3f (%d)\" % (m, se, n))"; date -u +%T
