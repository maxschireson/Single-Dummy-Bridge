# boxctl: timeout=180
set -euo pipefail
W="$HOME/work/rollout-experiments-20261114"
export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
git -C "$W/code" fetch -q origin research/stu-rollout-experiments-20261114
git -C "$W/code" worktree add --detach "$W/code-ben-4951fb0" 4951fb0b40adfcf85fe5cfc1b929f71f0ebc50e2
O="$W/ben-4951fb0"
mkdir "$O"
cp "$HOME/work/benconf/ben-64.conf" "$O/ben64.conf"
export STU_RUNTIME="$W/runtime" BRIDGE_NET_BF16=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PY="$HOME/work/loop/venv/bin/python"
"$PY" -m unittest discover -s "$W/code-ben-4951fb0/scripts/stu_rollout_experiments" -q > "$O/regressions.log" 2>&1
"$PY" "$W/code-ben-4951fb0/scripts/stu_rollout_experiments/make_config.py" --bots "$W/runtime/configs/loop-bots.json" --out "$O/bots.json"
python3 - "$O" <<'PY'
import pathlib,sys,json,hashlib,subprocess,configparser,time
o=pathlib.Path(sys.argv[1]);b=pathlib.Path.home()/'work/ben'
rev=subprocess.check_output(['git','-C',str(b),'rev-parse','HEAD'],text=True).strip()
assert rev=='9b5f43104aeac713a80b73513f2f2d6daf9f8769',rev
cfg=configparser.ConfigParser();cfg.read(o/'ben64.conf')
assert cfg.getint('dds','dds_max_threads')==1
assert cfg.getint('cardplay','sample_hands_play')==64
assert cfg.getint('sampling','sample_hands_opening_lead')==64
paths=[o/'ben64.conf',*sorted((b/'src').rglob('*.py'))]
for section in cfg.sections():
    for key,value in cfg.items(section):
        p=b/value
        if p.is_file():paths.append(p)
files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
p=dict(revision=rev,config=str(o/'ben64.conf'),files=files,
       dirty=subprocess.check_output(['git','-C',str(b),'status','--short'],text=True),
       tensorflow='2.21.0',dds_threads=1,tf_intra_threads=1,tf_inter_threads=1,
       cardplay_samples=64,opening_lead_samples=64,recorded=time.strftime('%FT%TZ',time.gmtime()))
(o/'ben-provenance.json').write_text(json.dumps(p,indent=2))
bots=json.loads((o/'bots.json').read_text());bots['rx-ben64']=dict(base='ben64',engine='ben',samples=64,url='http://127.0.0.1:8181',config=str(o/'ben64.conf'))
(o/'bots.json').write_text(json.dumps(bots,indent=2))
(o/'PLAN.json').write_text(json.dumps(dict(purpose='BEN development comparison requested by Max; common bidder, paired seats and fresh deal families',source='4951fb0b40adfcf85fe5cfc1b929f71f0ebc50e2',pilot=dict(first=7000,deals=8),screen=dict(first=8000,deals=256,chunks=8,chunk_size=32),seed=2026111401,workers=8,arms=['rx2-control','rx2-recursive32'],opponent='rx-ben64',training_excluded=True,deadline='2026-11-15T02:59:00Z',no_promotion=True),indent=2))
print(json.dumps(dict(revision=rev,hashed_files=len(files),dirty=p['dirty'])))
PY
cat > "$W/ben-batch-4951fb0.py" <<'PY'
import datetime,hashlib,json,pathlib,socket,subprocess,time,os
w=pathlib.Path.home()/'work/rollout-experiments-20261114';o=w/'ben-4951fb0';h=w/'code-ben-4951fb0/scripts/stu_rollout_experiments'
py=pathlib.Path.home()/'work/loop/venv/bin/python'
benpy=pathlib.Path.home()/'work/ben-venv/bin/python';ben=pathlib.Path.home()/'work/ben'
deadline=datetime.datetime(2026,11,15,2,59,tzinfo=datetime.timezone.utc).timestamp()
def left():return int(deadline-time.time())
def note(status,**kw):
    p=o/'STATUS.json';q=p.with_suffix('.tmp')
    q.write_text(json.dumps(dict(status=status,updated=time.strftime('%FT%TZ',time.gmtime()),**kw),indent=2));q.replace(p)
def verify():
    p=json.loads((o/'ben-provenance.json').read_text())
    for f,sha in p['files'].items():assert hashlib.sha256(pathlib.Path(f).read_bytes()).hexdigest()==sha,f
def run(arm,name,first,deals):
    assert left()>120
    verify();note('running',arm=arm,run=name,first=first,deals=deals)
    cmd=[str(py),str(h/'match.py'),'--source',str(pathlib.Path.home()/'work/loop/capsule/recovery'),'--bots',str(o/'bots.json'),'--pair',arm+'~rx-ben64','--seed','2026111401','--first',str(first),'--deals',str(deals),'--workers','8','--recycle','4','--common-only','--episodes','--out',str(o/name),'--ben-urls',','.join('http://127.0.0.1:'+str(8181+i) for i in range(8)),'--ben-provenance',str(o/'ben-provenance.json')]
    with (o/(name+'.log')).open('x') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=max(1,left()-30))
    s=json.loads((o/name/'summary.json').read_text())
    assert s['boards']==deals and s['failures']==0 and not s['driver_failure'],s
    rows=[json.loads(l) for l in (o/name/'results.jsonl').read_text().splitlines()]
    assert all(len(r['ben_endpoints'])==1 for r in rows)
units=[]
try:
    note('waiting for complete guarantee512 handoff')
    while left()>600:
        p=w/'BEN_HANDOFF.json'
        if p.exists() and json.loads(p.read_text()).get('status')=='ready':break
        time.sleep(15)
    else:raise RuntimeError('No clean handoff before deadline')
    while subprocess.run(['systemctl','is-active','--quiet','stu-rollout-publish']).returncode==0:
        if left()<600:raise RuntimeError('Old publisher still active')
        time.sleep(5)
    verify()
    for i in range(8):
        port=8181+i
        with socket.socket() as s:s.bind(('127.0.0.1',port))
        unit='stu-rollout-ben-server-'+str(i+1);units.append(unit)
        subprocess.run(['sudo','systemd-run','--unit='+unit,'--uid=bridgebots','--property=RuntimeMaxSec='+str(max(1,left()-10)),'--property=WorkingDirectory='+str(ben),
           '--setenv=HOME='+str(pathlib.Path.home()),'--setenv=PYTHONUNBUFFERED=1','--setenv=OPENBLAS_NUM_THREADS=1','--setenv=OMP_NUM_THREADS=1','--setenv=MKL_NUM_THREADS=1',
           '--setenv=TF_NUM_INTRAOP_THREADS=1','--setenv=TF_NUM_INTEROP_THREADS=1','--setenv=TF_CPP_MIN_LOG_LEVEL=3',
           str(benpy),'src/gameapi.py','--config',str(o/'ben64.conf'),'--host','127.0.0.1','--port',str(port),'--record','false'],check=True)
    t=time.time()+180
    pending=set(range(8))
    while pending and time.time()<t:
        for i in list(pending):
            try:
                with socket.create_connection(('127.0.0.1',8181+i),timeout=1):pending.remove(i)
            except OSError:pass
        if pending:time.sleep(2)
    assert not pending,('BEN startup failed',pending)
    for arm,label in [('rx2-recursive32','recursive32'),('rx2-control','flat128')]:
        run(arm,'pilot-'+label,7000,8)
    note('pilot passed; starting prespecified 256-board panel')
    for chunk in range(8):
        for arm,label in [('rx2-control','flat128'),('rx2-recursive32','recursive32')]:
            run(arm,'screen-'+str(chunk).zfill(2)+'-'+label,8000+32*chunk,32)
    note('complete')
except BaseException as e:
    note('failed or budget expired',error=repr(e));raise
finally:
    for unit in units:
        p=subprocess.run(['systemctl','show',unit,'-p','CPUUsageNSec','-p','MemoryPeak','-p','ActiveState','-p','Result'],capture_output=True,text=True)
        (o/(unit+'.txt')).write_text(p.stdout)
        subprocess.run(['sudo','systemctl','stop','--no-block',unit])
PY
cat > "$W/run-ben-4951fb0.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
W="$HOME/work/rollout-experiments-20261114"
export STU_RUNTIME="$W/runtime" SURE_BIN="$HOME/work/loop/bin/sure_cpp"
export BRIDGE_NET_BF16=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=''
exec /usr/bin/python3 "$W/ben-batch-4951fb0.py" > "$W/ben-4951fb0/batch.log" 2>&1
SH
sudo systemd-run --unit=stu-rollout-ben-4951fb0 --uid=bridgebots --property=RuntimeMaxSec=16500 --property=WorkingDirectory="$W" /bin/bash "$W/run-ben-4951fb0.sh"
systemctl show stu-rollout-ben-4951fb0 -p Id -p ActiveState -p MainPID
cat "$O/regressions.log"
