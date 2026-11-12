# boxctl: timeout=120
#!/bin/bash
W=$HOME/work; G=$W/g8p41; P=$W/p41; PY=$W/venv/bin/python; R=$P/runs/reading_reports
cat > $P/mech.sh <<'EOS'
#!/bin/bash
W=$HOME/work; G=$W/g8p41; P=$W/p41; PY=$W/venv/bin/python; R=$P/runs/reading_reports
cd $G; export OPENBLAS_NUM_THREADS=1 BRIDGE_DDS_CACHE=
$PY scripts/gen8_reading_bench.py cards --out $P/runs/reading --episodes $P/epsB > $P/logs/cards.out 2>&1
echo "cards exit $? $(date -u +%T)" >> $P/logs/timeline.log
$PY scripts/gen8_reading_bench.py report --out $P/runs/reading --mechanism --json $R/t2-mechanism.json > $R/t2-mechanism.txt 2>&1
echo "mechanism report exit $? $(date -u +%T)" >> $P/logs/timeline.log
cp $P/logs/bench_v0.log $R/bench_v0.txt; cp $P/logs/bench_l32.log $R/bench_l32.txt
bash $P/pushrd.sh
EOS
chmod +x $P/mech.sh
sudo systemd-run --unit=g8-mech --uid="$(id -un)" --working-directory="$G" --setenv=HOME="$HOME" -- /bin/bash $P/mech.sh 2>&1 | tail -1
head -c 1500 $P/logs/bench_v0.log; echo; grep -c . $P/logs/bench_v0.log; $PY - <<'PYEOF'
import json, os
for n in ('bench_v0', 'bench_l32'):
    d = json.load(open(os.path.expanduser(f'~/work/p41/runs/{n}/rows.json')))
    rows = d['rows'] if isinstance(d, dict) else d
    print(n, type(d).__name__, list(d)[:8] if isinstance(d, dict) else '', len(rows), 'pairs', len({r['family'] for r in rows}), 'deals', sorted(k for k in rows[0] if k.startswith('tree') or k.startswith('pimc')))
PYEOF
