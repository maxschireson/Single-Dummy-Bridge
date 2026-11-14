W=$HOME/work/loop; grep MATCH $W/human.log | tail -n +4 | cut -c1-200; cd $W/exp-human; $W/venv/bin/python - <<PY
import json, os
for t in ("m10","m10h","m10h4"):
    if not os.path.exists(f"{t}/metrics.json"): continue
    m=json.load(open(f"{t}/metrics.json"))
    print(t, m["train_examples"], " ".join("%d: %.4f/%.4f/%.4f" % (h["epoch"], h["val"]["nll"], h["val"]["agree"], h["val"]["regret"]) for h in m["history"]))
    c=list(m["compared"].values())[0]["all"]; print("   r3 there: %.4f/%.4f/%.4f" % (c["nll"], c["agree"], c["regret"]))
PY
grep "stage\|failed\|net " $W/human.log | tail -3 | cut -c1-200; date -u +%T
