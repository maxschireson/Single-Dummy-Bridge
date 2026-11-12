# boxctl: timeout=400
#!/bin/bash
W=$HOME/work; G=$W/g8p41; P=$W/p41; PY=$W/venv/bin/python
cd $G && git fetch -q --depth=1 origin feature/gen8-p41-20261112 && git show FETCH_HEAD:scripts/gen8_reading_bench.py > scripts/gen8_reading_bench.py
mkdir -p $P/runs/reading_reports
OPENBLAS_NUM_THREADS=1 $PY scripts/gen8_reading_bench.py report --out $P/runs/reading --json $P/runs/reading_reports/interim.json > $P/runs/reading_reports/interim.txt 2>&1
cut -c1-330 $P/runs/reading_reports/interim.txt | head -120
date -u +%T; tail -2 $P/logs/timeline.log
