# boxctl: timeout=600
#!/bin/bash
W=$HOME/work; G=$W/g8p41; P=$W/p41; PY=$W/venv/bin/python; R=$P/runs/reading_reports
cd $G && git fetch -q --depth=1 origin feature/gen8-p41-20261112 && git show FETCH_HEAD:scripts/gen8_reading_bench.py > scripts/gen8_reading_bench.py
date -u +%T; uptime; systemctl list-units --no-legend "g8-*" "p41-*" | cut -c1-80
export OPENBLAS_NUM_THREADS=1
( $PY scripts/gen8_reading_bench.py report --out $P/runs/reading --against v4 --pairs-only > $R/t2-against-v4.txt 2>&1 ) &
( $PY scripts/gen8_reading_bench.py report --out $P/runs/reading --against v4.1 --pairs-only > $R/t2-against-v41.txt 2>&1 ) &
wait
grep "  all \|before the deal\|  deal list " $R/t2-against-v4.txt | cut -c1-210
echo; grep "  all " $R/t2-against-v41.txt | cut -c1-210
echo; tail -5 $P/logs/bench_v0.log | cut -c1-400; echo; tail -5 $P/logs/bench_l32.log | cut -c1-400; ls -la $P/runs/bench_v0 $P/runs/bench_l32 | awk '{print $5, $9}'
