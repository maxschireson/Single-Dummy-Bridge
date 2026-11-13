# boxctl: timeout=120
cd ~/work/x8/runs; ~/work/venv/bin/python - <<EOF
import json, numpy as np
R = {z: {json.loads(l)["index"]: json.loads(l) for l in open(z + "/results.jsonl")} for z in ("z3", "z4", "z5")}
for z, r in R.items():
    x = np.array([v["common"] for v in r.values() if v.get("common") is not None], float)
    print(z, len(x), "%+.3f +- %.3f" % (x.mean(), x.std(ddof=1)/np.sqrt(len(x))))
ix = sorted(set(R["z3"]) & set(R["z5"]))
d = np.array([R["z3"][i]["common"] - R["z5"][i]["common"] for i in ix], float)
print("z3 - z5 paired", len(ix), "%+.3f +- %.3f" % (d.mean(), d.std(ddof=1)/np.sqrt(len(d))))
EOF
