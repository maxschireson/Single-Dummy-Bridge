# boxctl: timeout=120
cd ~/work/x8/src && wc -l < ../runs/x1/results.jsonl; tail -1 ../runs/x1.log | cut -c1-200; ~/work/venv/bin/python - <<EOF
import json, numpy as np
rows = [json.loads(l) for l in open("../runs/x1/results.jsonl")]
x = np.array([r["common"] for r in rows if r.get("common") is not None], float)
print("boards", len(rows), "IMPs/board %+.3f +- %.3f" % (x.mean(), x.std(ddof=1)/np.sqrt(len(x))), "won", (x>0).sum(), "lost", (x<0).sum(), "cpu/board", round(np.mean([r["cpu"] for r in rows]),1))
EOF
~/work/venv/bin/python scripts/x8_forks.py ../runs/x1 2>&1 | head -24
