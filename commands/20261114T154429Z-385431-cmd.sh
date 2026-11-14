W=$HOME/work/loop; for r in h4c3-n h4c-pst; do f=$W/runs/$r/results.jsonl; [ -f $f ] && python3 -c "
import json,sys
v=[json.loads(l)[\"common\"] for l in open(\"$f\") if l.strip()]
n=len(v); m=sum(v)/max(n,1); se=(sum((x-m)**2 for x in v)/max(n-1,1)/max(n,1))**.5
print(\"$r %+.3f +- %.3f (%d)\" % (m, se, n))"; done; tail -n 2 $W/runs.log | cut -c1-160; date -u +%T
