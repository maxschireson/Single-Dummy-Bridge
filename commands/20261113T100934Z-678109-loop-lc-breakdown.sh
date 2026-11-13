echo "# loop: learning-curve breakdown by phase and side (read-only)"; ~/work/loop/venv/bin/python - <<"PY"
import json, os
L = os.path.expanduser("~/work/loop/lc")
def show(tag, v):
    parts = []
    for k in ("declaring", "defending"):
        parts.append(f"{k} nll {v[k][\"nll\"]:.3f} agree {v[k][\"agree\"]:.3f} n {v[k][\"n\"]}")
    for k, s in v["by_phase"].items():
        parts.append(f"{k} nll {s[\"nll\"]:.3f} agree {s[\"agree\"]:.3f}")
    print(tag, "|", " | ".join(parts))
b = json.load(open(f"{L}/run-base/metrics.json")); f1 = json.load(open(f"{L}/run-f1/metrics.json"))
show("v2 as 8s-32 ", b["validation"]); show("523 boards  ", f1["validation"])
for k, v in b["compared"].items():
    show(os.path.basename(k)[:12], v)
print("epochs of the 523-board run:", [(h["epoch"], h["val"]["nll"], h["val"]["agree"], h["val"]["regret"]) for h in f1["history"]])
print("gap head: regret_gap_head base", b["validation"]["all"]["regret_gap_head"], "after 523 boards", f1["validation"]["all"]["regret_gap_head"], "| in_best", b["validation"]["all"]["in_best"], f1["validation"]["all"]["in_best"])
t = f1["validation"]["from_trick_7"]; t0 = b["validation"]["from_trick_7"]
print("from trick 7: in_best", t0["in_best"], t["in_best"], "regret", t0["regret"], t["regret"], "regret_gap_head", t0["regret_gap_head"], t["regret_gap_head"], "regret_random", t["regret_random"])
PY
