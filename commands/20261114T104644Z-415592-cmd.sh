W=$HOME/work/loop; grep MATCH $W/human.log | tail -n +10 | cut -c1-200; cd $W/exp-human; $W/venv/bin/python - <<PY
import json, os
for t in ("m10F",):
    if not os.path.exists(f"{t}/metrics.json"): continue
    m=json.load(open(f"{t}/metrics.json"))
    print(t, m["train_examples"], " ".join("%d: %.4f/%.4f/%.4f" % (h["epoch"], h["val"]["nll"], h["val"]["agree"], h["val"]["regret"]) for h in m["history"]))
PY
grep "failed\|net m10F\|stage fit" $W/human.log | tail -3 | cut -c1-200; tail -n 2 $W/runs.log | cut -c1-150; for r in xh-m10h4-p xh-m10F-n; do echo "$r $(wc -l < $W/runs/$r/results.jsonl 2>/dev/null)"; done | tr "\n" " "; date -u +%T
