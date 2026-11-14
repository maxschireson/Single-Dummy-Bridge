W=$HOME/work/loop; cat $W/runs/bu3-pst200[a-e]-[1-8]/results.jsonl | python3 -c "
import sys, json
v=[json.loads(l)[\"common\"] for l in sys.stdin if l.strip()]
n=len(v); m=sum(v)/n; se=(sum((x-m)**2 for x in v)/(n-1)/n)**.5
print(\"bu3 all blocks: %+.3f +- %.3f (%d deals)\" % (m, se, n))"; cat $W/runs/bu4-pst200a-[1-8]/results.jsonl 2>/dev/null | wc -l; date -u +%T
