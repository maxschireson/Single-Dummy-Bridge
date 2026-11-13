# boxctl: timeout=120
W=$HOME/work/x8; PY=$HOME/work/venv/bin/python; tail -3 $W/queue.log; for z in z3 z4 z5; do echo "== $z: $(tail -1 $W/runs/$z.log | cut -c1-140)"; done; $PY /tmp/x8_forks_trick.py $W/runs/z3 | head -42
