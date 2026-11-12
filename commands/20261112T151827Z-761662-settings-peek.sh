# boxctl: timeout=60
# Read-only: the settings matches so far (common bidding = the IMPs of the two tables with the same auction).
X=$HOME/work/settings; date -u +%T; echo "match-m1 $(systemctl is-active match-m1); match-m3 $(systemctl is-active match-m3); settings-pub $(systemctl is-active settings-pub)"
python3 - "$X" <<'PY'
import json, math, sys
x = sys.argv[1]
for m in ('m1', 'm3'):
    try: rows = [json.loads(l) for l in open(f'{x}/{m}/results.jsonl')]
    except Exception as e: print(m, 'no results', e); continue
    for reg in ('common', 'native'):
        v = [r[reg] for r in rows if r.get(reg) is not None]
        n = len(v); mu = sum(v) / n if n else float('nan'); sd = math.sqrt(sum((a - mu) ** 2 for a in v) / (n - 1)) if n > 1 else float('nan')
        print(f"{m} {rows[0]['candidate'] if rows else ''}~{rows[0]['opponent'] if rows else ''} {reg}: {n} boards, {mu:+.3f} +- {sd / math.sqrt(n):.3f}, won {sum(a > 0 for a in v)}, lost {sum(a < 0 for a in v)}")
    print(f"   cpu a board {sum(r['cpu'] for r in rows) / max(1, len(rows)):.1f}s")
PY
