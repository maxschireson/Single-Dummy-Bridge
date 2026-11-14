# boxctl: timeout=120
set -eu
python3 - <<'PY'
import subprocess, pathlib, json
h=pathlib.Path.home(); w=h/'work/loop'
for line in subprocess.check_output(['ps','-eo','pid,ppid,etimes,comm,args'],text=True).splitlines():
    if ('scripts/x8_match.py' in line or 'chain.sh' in line) and 'bash -l' not in line: print(line)
for p in [w/'RECYCLE',w/'src/training/rollout-loop-20261113/jobs-azure6.txt']:
    print(str(p),p.read_text() if p.exists() else 'missing')
for name in ['sp4tb','sp3tb']:
    r=w/'runs'/name
    for f in ['manifest.json','summary.json']:
        p=r/f
        if p.exists():
            d=json.loads(p.read_text())
            print(name,f,json.dumps(d)[:3500])
print('model', list((w/'src/models/cardplay/stu-net-r4c-20261113').glob('*')))
print('episode sample', list((w/'runs/sp4tb/episodes').glob('*.json.gz'))[:3])
PY
