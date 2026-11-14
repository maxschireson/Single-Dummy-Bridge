# boxctl: timeout=120
set -euo pipefail
W="$HOME/work/rollout-experiments-20261114"
mkdir -p "$W"
cat > "$W/drain.py" <<'PY'
import json, os, pathlib, signal, subprocess, time
w=pathlib.Path.home()/'work/rollout-experiments-20261114'
unit='loop-collect.service'
pids=subprocess.check_output(['ps','-eo','pid,args'],text=True).splitlines()
parents=[]
for line in pids:
    fields=line.strip().split(None,1)
    if len(fields)<2: continue
    pid=int(fields[0]); cmd=fields[1]
    if 'python scripts/x8_match.py' in cmd and '/runs/sp4tb ' in cmd:
        parents.append(pid)
def children(pid):
    try: return [int(x) for x in pathlib.Path(f'/proc/{pid}/task/{pid}/children').read_text().split()]
    except FileNotFoundError: return []
candidates=[pid for pid in parents if len(children(pid))>=4]
if len(candidates)!=1: raise RuntimeError(f'expected one active sp4tb parent, got {candidates}')
pid=candidates[0]
main=int(subprocess.check_output(['systemctl','show',unit,'-p','MainPID','--value'],text=True))
start=time.monotonic()
status=dict(parent=pid,unit_main=main,started=time.strftime('%FT%TZ',time.gmtime()),status='waiting-for-recycle-boundary')
(w/'drain-status.json').write_text(json.dumps(status,indent=2))
while time.monotonic()-start<1200:
    if not pathlib.Path(f'/proc/{pid}').exists(): raise RuntimeError('parent changed; manual review needed')
    if children(pid):
        time.sleep(.005); continue
    os.kill(pid,signal.SIGSTOP)
    if children(pid):
        os.kill(pid,signal.SIGCONT); time.sleep(.005); continue
    os.kill(main,signal.SIGSTOP)
    run=pathlib.Path.home()/'work/loop/runs/sp4tb'
    rows=(run/'results.jsonl').read_text().splitlines()
    status.update(status='drained',finished=time.strftime('%FT%TZ',time.gmtime()),
                  rows=len(rows),episodes=len(list((run/'episodes').glob('*.json.gz'))),
                  source=subprocess.check_output(['git','-C',str(pathlib.Path.home()/'work/loop/src'),'rev-parse','HEAD'],text=True).strip())
    (w/'collection-resume.json').write_text(json.dumps(dict(status,run=str(run),command=next(x for x in pids if x.strip().startswith(str(pid)+' '))),indent=2))
    subprocess.run(['sudo','systemctl','stop','--no-block',unit],check=True)
    for p in (pid,main):
        try: os.kill(p,signal.SIGCONT)
        except ProcessLookupError: pass
    (w/'drain-status.json').write_text(json.dumps(status,indent=2))
    print(json.dumps(status),flush=True)
    break
else:
    status['status']='timeout-collector-left-running'
    (w/'drain-status.json').write_text(json.dumps(status,indent=2))
    raise RuntimeError(status['status'])
PY
sudo systemd-run --unit=stu-rollout-drain --uid="$USER" --property=RuntimeMaxSec=1250 "$HOME/work/loop/venv/bin/python" "$W/drain.py"
systemctl show stu-rollout-drain -p ActiveState -p MainPID
