W=$HOME/work/loop; grep MATCH $W/human.log | cut -c1-200; grep "stage\|failed" $W/human.log | tail -4 | cut -c1-200; cd $W/exp-human; $W/venv/bin/python - <<PY
import json
for t in ("hf","bf","mf","hs-score","bs-score"):
    m=json.load(open(f"{t}/metrics.json")); v=m["validation"]["all"] if t.endswith("score") else m["history"][-1]["val"]
    print(t, {k: v.get(k) for k in ("n","searched","nll","agree","in_best","rated_pick","regret","regret_gap_head","regret_random")})
    if t in ("hf","bf","mf"):
        c=list(m["compared"].values())[0]["all"]; print("   r3", {k: c.get(k) for k in ("nll","agree","in_best","rated_pick","regret")})
        bp=m["validation"]["by_phase"]; print("   by phase (selected epoch)", {p: (x["regret"], x["searched"]) for p,x in bp.items()})
PY
date -u +%T
