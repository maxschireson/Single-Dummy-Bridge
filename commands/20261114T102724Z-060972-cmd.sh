W=$HOME/work/loop; grep MATCH $W/human.log | tail -n +7 | cut -c1-200; cd $W/exp-human; $W/venv/bin/python - <<PY
import json, os
for t in ("s10","s10h"):
    if not os.path.exists(f"{t}/metrics.json"): continue
    m=json.load(open(f"{t}/metrics.json"))
    print(t, m["train_examples"], " ".join("%d: %.4f/%.4f/%.4f" % (h["epoch"], h["val"]["nll"], h["val"]["agree"], h["val"]["regret"]) for h in m["history"]), "kept", m["selected_epoch"])
    c=list(m["compared"].values())[0]["all"]; print("   r3 there: %.4f/%.4f/%.4f" % (c["nll"], c["agree"], c["regret"]))
PY
grep "stage\|failed\|net s" $W/human.log | tail -3 | cut -c1-200; tail -n 2 $W/runs.log | cut -c1-150; wc -l $W/runs/xh-hf-n/results.jsonl | cut -d" " -f1; date -u +%T
