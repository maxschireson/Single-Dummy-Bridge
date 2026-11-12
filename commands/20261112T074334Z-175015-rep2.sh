# boxctl: timeout=100
#!/bin/bash
W=$HOME/work; G=$W/g8p41; P=$W/p41; PY=$W/venv/bin/python
cd $G && git fetch -q --depth=1 origin feature/gen8-p41-20261112 && git show FETCH_HEAD:scripts/gen8_reading_bench.py > scripts/gen8_reading_bench.py
mkdir -p $P/runs/reading_reports
cat > $P/report.sh <<'EOS'
#!/bin/bash
# report.sh TAG : snapshot the finished parts and report on the snapshot (plain, sweep, owner head)
W=$HOME/work; G=$W/g8p41; P=$W/p41; PY=$W/venv/bin/python; R=$P/runs/reading_reports; T=$1
cd $G
export OPENBLAS_NUM_THREADS=1
S=$P/runs/reading_snap_$T; rm -rf $S; mkdir -p $S
for f in $P/runs/reading/pools-*-*.npz; do [ -e ${f/pools-/own-} ] && ln $f $S/ && ln ${f/pools-/own-} $S/; done
$PY scripts/gen8_reading_bench.py report --out $S --json $R/$T.json > $R/$T.txt 2>&1 &
$PY scripts/gen8_reading_bench.py report --out $S --house --json $R/$T-house.json > $R/$T-house.txt 2>&1 &
$PY scripts/gen8_reading_bench.py report --out $S --sweep --json $R/$T-sweep.json > $R/$T-sweep.txt 2>&1 &
$PY scripts/gen8_reading_bench.py report --out $S --owner 0.25 --owner 0.5 --owner 1 --json $R/$T-owner.json > $R/$T-owner.txt 2>&1 &
wait
echo "report $T done $(date -u +%T)" >> $P/logs/timeline.log
EOS
chmod +x $P/report.sh
date -u +%T; tail -3 $P/logs/timeline.log; ls $P/runs/reading/own-*.npz 2>/dev/null | wc -l; ls $P/runs/reading/pools-*-*.npz | wc -l; tail -2 $P/logs/owners.out; cat $P/logs/eval_direct.log | cut -c1-330
