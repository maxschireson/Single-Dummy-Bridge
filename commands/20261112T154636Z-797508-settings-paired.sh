# boxctl: timeout=60
# Read-only: the settings matches so far, each alone and paired board by board on the deals both have played.
X=$HOME/work/settings; date -u +%T
python3 - "$X" <<'PY'
import json, math, sys
x = sys.argv[1]
rows = {m: {r['index']: r['common'] for r in map(json.loads, open(f'{x}/{m}/results.jsonl')) if r.get('common') is not None} for m in ('m1', 'm3')}
def ms(v):
    n = len(v); mu = sum(v) / n; sd = math.sqrt(sum((a - mu) ** 2 for a in v) / (n - 1)); return n, mu, sd / math.sqrt(n)
for m, d in rows.items():
    n, mu, se = ms(list(d.values())); print(f"{m}: {n} boards, {mu:+.3f} +- {se:.3f}, flat {sum(v == 0 for v in d.values())}")
both = sorted(set(rows['m1']) & set(rows['m3']))
a = [rows['m1'][i] for i in both]; b = [rows['m3'][i] for i in both]
n, mu, se = ms([p - q for p, q in zip(a, b)])
ma = sum(a) / n; mb = sum(b) / n; va = sum((p - ma) ** 2 for p in a); vb = sum((q - mb) ** 2 for q in b)
r = sum((p - ma) * (q - mb) for p, q in zip(a, b)) / math.sqrt(va * vb)
print(f"same {n} deals: m1 {ma:+.3f}, m3 {mb:+.3f}, m1 minus m3 {mu:+.3f} +- {se:.3f}; board-by-board correlation {r:.2f}; boards identical in both {sum(p == q for p, q in zip(a, b))}")
PY
