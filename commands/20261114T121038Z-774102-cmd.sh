W=$HOME/work/loop; grep MATCH $W/human.log | tail -n +18 | cut -c1-200; grep "failed\|net sAh" $W/human.log | tail -2 | cut -c1-160; cd $W/exp-human; $W/venv/bin/python - <<PY
import json, os
for t in ("sAh",):
    if not os.path.exists(f"{t}/metrics.json"): continue
    m=json.load(open(f"{t}/metrics.json"))
    print(t, m["train_examples"], " ".join("%d: %.4f/%.4f/%.4f" % (h["epoch"], h["val"]["nll"], h["val"]["agree"], h["val"]["regret"]) for h in m["history"]))
PY
tail -n 2 $W/runs.log | cut -c1-150; tail -n 2 $W/r4arena/arena.log | cut -c1-160; echo "xh-hf-p $(wc -l < $W/runs/xh-hf-p/results.jsonl)"; date -u +%T
