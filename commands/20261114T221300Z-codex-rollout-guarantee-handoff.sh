# boxctl: timeout=90
set -euo pipefail
W="$HOME/work/rollout-experiments-20261114"
cat > "$W/finish-guarantee.py" <<'PY'
import json,os,pathlib,select,signal,subprocess,time
w=pathlib.Path.home()/'work/rollout-experiments-20261114'
parent=int(subprocess.check_output(['systemctl','show','stu-rollout-experiments','-p','MainPID','--value']))
children=pathlib.Path(f'/proc/{parent}/task/{parent}/children').read_text().split()
matches=[int(p) for p in children if b'rx-guarantee~rx-control' in pathlib.Path(f'/proc/{p}/cmdline').read_bytes()]
assert len(matches)==1, (parent,children)
child=matches[0]; fd=os.pidfd_open(child)
os.kill(parent,signal.SIGSTOP)
note=dict(parent=parent,match=child,status='waiting for guarantee512 to finish',started=time.strftime('%FT%TZ',time.gmtime()))
(w/'BEN_HANDOFF.json').write_text(json.dumps(note,indent=2))
try:
    if not select.select([fd],[],[],2700)[0]:raise RuntimeError('Guarantee completion deadline')
    p=w/'runs/mechanism-guarantee/summary.json'; s=json.loads(p.read_text())
    assert s['boards']==512 and s['failures']==0,s
    subprocess.run(['sudo','systemctl','stop','--no-block','stu-rollout-experiments'],check=True)
    try:os.kill(parent,signal.SIGCONT)
    except ProcessLookupError:pass
    note.update(status='ready',finished=time.strftime('%FT%TZ',time.gmtime()),summary=s,combined_deferred=True)
    (w/'BEN_HANDOFF.json').write_text(json.dumps(note,indent=2))
except BaseException:
    try:os.kill(parent,signal.SIGCONT)
    except ProcessLookupError:pass
    raise
finally:os.close(fd)
PY
sudo systemd-run --unit=stu-rollout-guarantee-handoff --uid=bridgebots --property=RuntimeMaxSec=2800 /usr/bin/python3 "$W/finish-guarantee.py"
cat "$HOME/work/benconf/ben-64.conf"
python3 - "$HOME/work/loop/capsule/recovery/manifest.json" <<'PY'
import json,sys
m=json.load(open(sys.argv[1])); print(json.dumps({k:v for k,v in m['bots'].items() if v.get('engine')=='ben'},indent=2))
PY
