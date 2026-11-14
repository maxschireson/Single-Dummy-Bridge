W=$HOME/work/loop; grep MATCH $W/human.log | tail -n +17 | cut -c1-200; grep "failed\|net [hbs]A" $W/human.log | tail -3 | cut -c1-160; for t in bA sAh; do grep -o "\"epoch\": [0-9], \"seconds\": [0-9]*" $W/exp-human/$t.log 2>/dev/null | tail -1; done; cd $W/exp-human; $W/venv/bin/python - <<PY
import json, os
for t in ("hA","bA","sAh"):
    if not os.path.exists(f"{t}/metrics.json"): continue
    m=json.load(open(f"{t}/metrics.json"))
    print(t, m["train_examples"], " ".join("%d: %.4f/%.4f/%.4f" % (h["epoch"], h["val"]["nll"], h["val"]["agree"], h["val"]["regret"]) for h in m["history"]))
PY
tail -n 1 $W/runs.log | cut -c1-150; echo "xh-hs-p $(wc -l < $W/runs/xh-hs-p/results.jsonl)"; date -u +%T
