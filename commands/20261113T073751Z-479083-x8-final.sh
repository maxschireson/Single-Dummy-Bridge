# boxctl: timeout=200
W=$HOME/work/x8; PY=$HOME/work/venv/bin/python; sudo systemctl stop x8-queue7 x8-queue8; sleep 3; pkill -f "x8_match.py --feature-forks" || true; sleep 2; for z in x6 x4; do echo "$(date -u +%FT%TZ) $z stopped at $(wc -l < $W/runs/$z/results.jsonl) boards: azure6 back to the table session at 08:00 (allocation)" >> $W/queue.log; done; $PY - <<"P"
import json, math, os
W = os.environ["HOME"] + "/work/x8/runs/"
def ms(v):
    n = len(v); m = sum(v)/n; return n, m, (math.sqrt(sum((x-m)**2 for x in v)/(n-1)/n) if n > 1 else 0)
idx = {}
for z in ("x1", "x4", "x5", "x6"):
    r = [json.loads(l) for l in open(W + z + "/results.jsonl")]
    idx[z] = {x["index"]: x["common"] for x in r}
    n, m, s = ms(list(idx[z].values())); cpu = sum(x["cpu"] for x in r)/len(r)
    print(z, n, "%+.3f +- %.3f cpu %.1f" % (m, s, cpu))
for a, b in (("x4","x5"), ("x6","x5"), ("x4","x6"), ("x6","x1")):
    c = sorted(set(idx[a]) & set(idx[b])); n, m, s = ms([idx[a][k]-idx[b][k] for k in c])
    print(a, "-", b, "paired", n, "%+.3f +- %.3f" % (m, s))
P
for z in x6 x4; do echo "== $z"; $PY $W/bin/x8_forks.py $W/runs/$z > /tmp/f_$z.txt 2>&1; sed -n 2p /tmp/f_$z.txt; grep -A0 "^  with blend\|^  with guarantee\|^  with mix\|^  with claim" /tmp/f_$z.txt; done; grep -A2 "^  with blend" /tmp/f_x6.txt | tail -1; systemctl is-active x8-queue7 x8-queue8 || true
