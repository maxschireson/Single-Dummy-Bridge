# boxctl: timeout=300
#!/bin/bash
W=$HOME/work; P=$W/p41; S=$W/p41src; PY=$W/venv/bin/python; T=training/policy-v4.1-20261112
cd $S && git fetch -q --depth 1 origin transfer/gen7-policy-v4.1-20261112
for f in bench_report.py bench/bots.json; do mkdir -p $(dirname $T/$f); git show FETCH_HEAD:$T/$f > $T/$f; done
export OPENBLAS_NUM_THREADS=2
$PY $T/bench_report.py $P/runs/bench_v0/rows.json $T/bench/bots.json $P/runs/bench_v0/report 2>&1 | cut -c1-400
echo ---- A: v4 tree
cut -c1-250 $P/runs/bench_v0/report/sweep_v4.txt | head -45
echo ---- A: v0 tree "(labelled v4.1 by the script)"
cut -c1-250 $P/runs/bench_v0/report/sweep_v4.1.txt | head -45
