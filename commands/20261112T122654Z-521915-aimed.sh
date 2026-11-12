# boxctl: timeout=900
#!/bin/bash
W=$HOME/work; G=$W/g8p41; P=$W/p41; PY=$W/venv/bin/python; R=$P/runs/reading_reports
cd $G && git fetch -q --depth=1 origin feature/gen8-p41-20261112 && git show FETCH_HEAD:scripts/gen8_reading_bench.py > scripts/gen8_reading_bench.py
export OPENBLAS_NUM_THREADS=1
tail -3 $P/logs/timeline.log
# wait for the cards pass (it rewrites the uns files this report reads)
while ! grep -q "cards with scorer weights exit" $P/logs/timeline.log; do sleep 3; done
$PY scripts/gen8_reading_bench.py report --out $P/runs/reading --aim 1.05 --aim 1.85 --against v4 --json $R/t2-aimed-v4.json > $R/t2-aimed-v4.txt 2>&1
cut -c1-260 $R/t2-aimed-v4.txt
$PY scripts/gen8_reading_bench.py report --out $P/runs/reading --aim 1.05 --aim 1.85 --against v4.1 --json $R/t2-aimed-v41.json > $R/t2-aimed-v41.txt 2>&1
cut -c1-260 $R/t2-aimed-v41.txt
date -u +%T; tail -3 $P/logs/timeline.log
