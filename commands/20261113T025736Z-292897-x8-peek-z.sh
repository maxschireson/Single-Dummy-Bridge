# boxctl: timeout=120
cd ~/work/x8/runs; for z in z1 z2; do ~/work/venv/bin/python - $z <<EOF
import json, sys, numpy as np
z = sys.argv[1]
rows = [json.loads(l) for l in open(z + "/results.jsonl")]
x = np.array([r["common"] for r in rows if r.get("common") is not None], float)
c = [r["search"]["candidate"]["x8"] for r in rows]
print(z, "boards", len(rows), "IMPs/board %+.3f +- %.3f" % (x.mean(), x.std(ddof=1)/np.sqrt(len(x))), "cpu/board", round(np.mean([r["cpu"] for r in rows]),1),
      "per board: rollout decisions", round(np.mean([v["rollout"] for v in c]),1), "claims", round(np.mean([v["claim"] for v in c]),1), "forks", round(np.mean([len(r["search"].get("x8_forks") or []) for r in rows]),1))
EOF
done
