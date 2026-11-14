W=$HOME/work/loop; grep MATCH $W/human.log | tail -n +11 | cut -c1-200; cd $W/exp-human; $W/venv/bin/python - <<PY
import json, os
for t in ("m10A","m10B"):
    if not os.path.exists(f"{t}/metrics.json"): continue
    m=json.load(open(f"{t}/metrics.json"))
    print(t, m["train_examples"], " ".join("%d: %.4f/%.4f/%.4f" % (h["epoch"], h["val"]["nll"], h["val"]["agree"], h["val"]["regret"]) for h in m["history"]))
PY
grep "failed\|net m10[AB]" $W/human.log | tail -4 | cut -c1-160; for t in m10A m10B; do grep -o "\"epoch\": [0-9], \"seconds\": [0-9]*" $W/exp-human/$t.log 2>/dev/null | tail -1; done; tail -n 2 $W/runs.log | cut -c1-150; for r in xh-m10h4-p xh-m10h4-n; do echo "$r $(wc -l < $W/runs/$r/results.jsonl 2>/dev/null)"; done | tr "\n" " "; date -u +%T
