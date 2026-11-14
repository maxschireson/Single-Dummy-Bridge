grep "^{\"epoch\"" $HOME/work/loop/exp-width/w1536.log | python3 -c "
import sys, json
for l in sys.stdin:
    d = json.loads(l)
    if \"train_ce\" in d:
        v = d[\"val\"]; print(\"w1536 epoch\", d[\"epoch\"], \"sec\", d[\"seconds\"], \"train_ce\", d[\"train_ce\"], \"| nll\", v[\"nll\"], \"exact\", v[\"agree\"], \"tricks\", v[\"regret\"], \"gap-head\", v[\"regret_gap_head\"])
"; grep -v Warning $HOME/work/loop/exp-width/w1536.log | tail -n 1 | cut -c1-80
