# boxctl: timeout=300
#!/bin/bash
W=$HOME/work; P=$W/p41; S=$W/p41src; PY=$W/venv/bin/python; T=training/policy-v4.1-20261112; R=$P/runs/reading_reports
cd $S; export OPENBLAS_NUM_THREADS=2
echo "---- A, the tree with v4 (8 layouts)"; grep "realized cost of B\|correction sd\|== the tree" $P/runs/bench_v0/report/sweep_v4.txt | cut -c1-260
echo "---- A, the tree with v0 (labelled v4.1 by the script)"; grep "realized cost of B\|correction sd\|== the tree" $P/runs/bench_v0/report/sweep_v4.1.txt | cut -c1-260
# B: the tree with v4 on 32 layouts: keep Gen 6 decisions, then the same sweep
$PY - <<'PYEOF'
import json, os
P = os.path.expanduser('~/work/p41')
bots = json.load(open(os.path.expanduser('~/work/p41src/training/policy-v4.1-20261112/bench/bots.json')))
d = json.load(open(f'{P}/runs/bench_l32/rows.json'))
dec = lambda r: bots[r['family']][0] if r['player'] == 'candidate' else bots[r['family']][1]
kept = [r for r in d['rows'] if dec(r).startswith('6-')]
os.makedirs(f'{P}/runs/bench_l32/report', exist_ok=True)
json.dump(dict(settings=d['settings'], rows=kept), open(f'{P}/runs/bench_l32/report/rows_g6.json', 'w'))
print(len(d['rows']), 'pairs read;', len(kept), "at a Gen 6 bot's decision;", len({r['family'] for r in kept}), 'deals; bench ran', d['settings'].get('seconds'), 's')
PYEOF
K=tree_3_breadth3_mass0.98_path0.5_path_solves3000_plain1
$PY scripts/gen7_sweep.py $P/runs/bench_l32/report/rows_g6.json:$K --label "the tree with v4 on 32 layouts" --json $P/runs/bench_l32/report/sweep_v4_l32.json > $P/runs/bench_l32/report/sweep_v4_l32.txt 2>&1
echo "---- B, the tree with v4 on 32 layouts"; grep "realized cost of B\|correction sd\|== the tree" $P/runs/bench_l32/report/sweep_v4_l32.txt | cut -c1-260; sed -n 4,12p $P/runs/bench_l32/report/sweep_v4_l32.txt | cut -c1-150
echo "---- A grid rows, v4 then v0"; sed -n 4,12p $P/runs/bench_v0/report/sweep_v4.txt | cut -c1-150; sed -n 4,12p $P/runs/bench_v0/report/sweep_v4.1.txt | cut -c1-150
grep -A9 "this tree minus" $P/runs/bench_v0/report/sweep_v4.txt | head -10 | cut -c1-150
cp $P/runs/bench_v0/report/sweep_v4.txt $R/treeA_v4.txt; cp $P/runs/bench_v0/report/sweep_v4.1.txt $R/treeA_v0.txt; cp $P/runs/bench_l32/report/sweep_v4_l32.txt $R/treeB_v4_l32.txt
cp $P/runs/bench_v0/report/summary.json $R/treeA_summary.json
tail -3 $P/logs/timeline.log
