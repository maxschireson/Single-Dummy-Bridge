# boxctl: timeout=120
python3 -c "
import json, collections
m = json.load(open(\"/home/bridgebots/work/sidnet/data/fetchB.json\"))
nb = {k: v for k, v in m[\"new_by_branch\"].items() if v}
g = collections.Counter()
for k, v in nb.items():
    g[k.split(\"-azure\")[0].split(\"-codex\")[0].split(\"-independent\")[0][:26]] += v
print(\"branches with new episodes:\", len(nb), \"total\", sum(nb.values()))
print(dict(g.most_common(12)))
"
