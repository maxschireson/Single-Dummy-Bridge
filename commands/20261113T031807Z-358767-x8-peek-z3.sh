# boxctl: timeout=120
cd ~/work/x8/runs; for z in z3 z4 z5; do ~/work/venv/bin/python - $z <<EOF
import json, sys, numpy as np
z = sys.argv[1]
rows = [json.loads(l) for l in open(z + "/results.jsonl")]
x = np.array([r["common"] for r in rows if r.get("common") is not None], float)
f = [g for r in rows for g in (r["search"].get("x8_forks") or [])]
print(z, rows[0]["candidate"] if rows else "", "v", rows[0]["opponent"] if rows else "", "boards", len(rows), "IMPs/board %+.3f +- %.3f" % (x.mean(), x.std(ddof=1)/np.sqrt(len(x))), "cpu", round(np.mean([r["cpu"] for r in rows]),1), "forks", len(f), "changed", sum(1 for g in f if g[3]), "fork IMPs", sum(g[3] for g in f))
EOF
done; grep -c failed z3.log z4.log z5.log
