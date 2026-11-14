python3 - <<EOF
import json
a = json.load(open("/tmp/score_v2train.json"))["v2"]["scores"]; b = json.load(open("/tmp/score_v2fresh.json"))["v2"]["scores"]
print("score keys:", list(a.keys()))
f = lambda s, k: ("%.4f" % s[k]) if s and s.get(k) is not None else "   -  "
def row(label, p, q):
    print("%-14s rows %7s / %6s | log-loss %s / %s | exact %s / %s | tricks given up %s / %s | gap head %s / %s" % (label, (p or {}).get("n", "-"), (q or {}).get("n", "-"), f(p, "nll"), f(q, "nll"), f(p, "agree"), f(q, "agree"), f(p, "regret"), f(q, "regret"), f(p, "regret_gap_head"), f(q, "regret_gap_head")))
print("trained-on rows / held-out rows")
row("all", a.get("all"), b.get("all")); row("from trick 7", a.get("from_trick_7"), b.get("from_trick_7"))
bb = a.get("by_bot", {}); cc = b.get("by_bot", {})
for bot in sorted(set(bb) | set(cc), key=lambda k: -(bb.get(k, {}).get("n", 0))):
    row("bot " + bot, bb.get(bot), cc.get(bot))
for k in a:
    if k.startswith("by_") and k != "by_bot": print(k, list(a[k].keys())[:8])
EOF
