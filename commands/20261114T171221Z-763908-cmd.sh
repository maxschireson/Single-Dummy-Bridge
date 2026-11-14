# boxctl: timeout=120
# loop session: a read-only look at round 4's gate (Max, 17:10 UTC: why would stu4 be behind, bad luck?): the paired
# differences by deal set, the size of the swings, and what a results row carries.
set -euo pipefail
W=$HOME/work/loop
python3 - "$W" <<'PY'
import json, glob, sys
W = sys.argv[1]
def rd(p):
    d = {}
    for f in glob.glob(p):
        for l in open(f):
            try:
                r = json.loads(l); d[r['index']] = r
            except Exception:
                pass
    return d
a = rd(W + '/runs/bu3-pst200*-[1-8]/results.jsonl'); b = rd(W + '/runs/bu4-pst200*-[1-8]/results.jsonl'); c = rd(W + '/runs/bu4c-pst200*-[1-8]/results.jsonl')
def ms(v):
    n = len(v); m = sum(v) / n
    return m, (sum((x - m) ** 2 for x in v) / (n - 1) / n) ** .5, n
g = lambda d, k: d[k]['common']
k4 = sorted(set(a) & set(b)); kc = set(a) & set(b) & set(c)
print('R4 - R3 all: %+.3f +- %.3f (%d)' % ms([g(b, k) - g(a, k) for k in k4]))
A = [k for k in k4 if k in kc]; B = [k for k in k4 if k not in kc]
print('  on deals R4c has played: %+.3f +- %.3f (%d)' % ms([g(b, k) - g(a, k) for k in A]))
if len(B) > 2: print('  on deals R4c has not played: %+.3f +- %.3f (%d)' % ms([g(b, k) - g(a, k) for k in B]))
print('R4c - R3: %+.3f +- %.3f (%d)' % ms([g(c, k) - g(a, k) for k in A]))
print('R4 - R4c: %+.3f +- %.3f (%d)' % ms([g(b, k) - g(c, k) for k in A]))
print('vs BEN, all 512: R3 %+.3f +- %.3f (%d)' % ms([g(a, k) for k in k4]), '| R4 %+.3f +- %.3f (%d)' % ms([g(b, k) for k in k4]))
print('vs BEN, deals R4c has played: R3 %+.3f +- %.3f (%d)' % ms([g(a, k) for k in A]), '| R4 %+.3f +- %.3f (%d)' % ms([g(b, k) for k in A]), '| R4c %+.3f +- %.3f (%d)' % ms([g(c, k) for k in A]))
d = sorted((g(b, k) - g(a, k), k) for k in k4)
nz = [x for x, _ in d if x]
print('R4 - R3: %d of %d deals differ; total %+.0f IMPs; swings of 10+: %d against R4 (%+.0f), %d for R4 (%+.0f)' % (
    len(nz), len(d), sum(nz), sum(1 for x in nz if x <= -10), sum(x for x in nz if x <= -10), sum(1 for x in nz if x >= 10), sum(x for x in nz if x >= 10)))
small = [x for x in nz if abs(x) < 10]
print('  swings under 10: %d deals, total %+.0f' % (len(small), sum(small)))
print('  worst for R4:', d[:8]); print('  best for R4:', d[-8:])
r = b[k4[0]]
print('row keys:', sorted(r.keys()))
print(json.dumps(r)[:1800])
PY
date -u +%T
