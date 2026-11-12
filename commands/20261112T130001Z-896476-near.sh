# boxctl: timeout=900
#!/bin/bash
W=$HOME/work; G=$W/g8p41; P=$W/p41; PY=$W/venv/bin/python; R=$P/runs/reading_reports
cd $G && git fetch -q --depth=1 origin feature/gen8-p41-20261112 && git show FETCH_HEAD:scripts/gen8_reading_bench.py > scripts/gen8_reading_bench.py
export OPENBLAS_NUM_THREADS=1
( $PY scripts/gen8_reading_bench.py report --out $P/runs/reading --near 0.05 --near 0.1 --near 0.2 --near 0.4 --near-split 0.2 --against v4 --json $R/t2-near-v4.json > $R/t2-near-v4.txt 2>&1 ) &
( $PY scripts/gen8_reading_bench.py report --out $P/runs/reading --near 0.05 --near 0.1 --near 0.2 --near 0.4 --near-split 0.2 --against v4.1 --json $R/t2-near-v41.json > $R/t2-near-v41.txt 2>&1 ) &
wait
cut -c1-250 $R/t2-near-v4.txt; echo; cut -c1-250 $R/t2-near-v41.txt
bash $P/pushrd.sh; date -u +%T; uptime | cut -c1-80
