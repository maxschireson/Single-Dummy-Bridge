W=$HOME/work/loop/exp-strong; ls $W; for n in mix-512 mix-768 strong-512 strong-768; do [ -f $W/$n.log ] && { echo "== $n"; grep "^{\"epoch\"" $W/$n.log | python3 -c "
import sys, json
for l in sys.stdin:
    d = json.loads(l)
    if \"train_ce\" in d: print(\" epoch\", d[\"epoch\"], \"sec\", d.get(\"seconds\"), \"train_ce\", d[\"train_ce\"], \"train_gap\", d[\"train_gap\"], \"| val nll\", d[\"val\"][\"nll\"], \"agree\", d[\"val\"][\"agree\"], \"regret\", d[\"val\"][\"regret\"], \"gap-head regret\", d[\"val\"][\"regret_gap_head\"])
"; head -c 300 $W/$n.log | head -3; }; done; python3 -c "
import json,glob
for f in sorted(glob.glob(\"$W/*/metrics.json\")):
    m = json.load(open(f)); print(f.split(\"/\")[-2], \"width\", m[\"width\"], \"params\", m[\"parameters\"], \"epochs\", m[\"epochs\"], \"lr\", m[\"lr\"], \"examples\", m[\"train_examples\"], \"init\", m.get(\"init\"), \"seconds\", m.get(\"seconds\"))
"
