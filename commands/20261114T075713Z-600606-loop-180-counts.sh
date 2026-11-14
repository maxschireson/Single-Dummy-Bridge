# boxctl: timeout=60
# boxctl: timeout=60
# loop session (read-only): collection counts and rates since each run started; the box's latest runs.log lines.
W=$HOME/work/loop
python3 - <<'PY'
import glob, os, time, json
W = os.path.expanduser('~/work/loop')
now = time.time()
for f in sorted(glob.glob(f'{W}/runs/*/results.jsonl'), key=os.path.getmtime)[-14:]:
    run = f.split('/')[-2]
    if not run.startswith(('sg8', 'sp3t', 's8-', 'sp3s')):
        continue
    n = sum(1 for _ in open(f)); man = f.replace('results.jsonl', 'manifest.json')
    t0 = os.path.getmtime(man) if os.path.exists(man) else now
    print(f'{run}: {n} {"tables" if run.startswith("sg8") or run.startswith("sp3") else "boards"}, since {time.strftime("%H:%M", time.gmtime(t0))}, last {time.strftime("%H:%M", time.gmtime(os.path.getmtime(f)))}, {n / max((os.path.getmtime(f) - t0) / 3600, 1e-3):.0f} an hour')
PY
grep -E "role from here|row publisher|start (sg8|sp3t|s8-)" $W/runs.log | tail -n 3 | cut -c1-140
