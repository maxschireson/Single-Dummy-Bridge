import json,os,subprocess,time,fcntl
from pathlib import Path
w=Path('/workspace/work');sp=w/'bridge-gen8-transition-state.json';t=json.loads(sp.read_text());r=Path(t['new_run']);src=Path(t['new_source']);pub=Path(t['new_publication']);python=w/'bridge-venv/bin/python'
def write(p,v):
    tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(v,indent=2)+'\n');tmp.replace(p)
def cmd(name):
    p=r/name
    if not p.exists():return ''
    f=Path('/proc')/str(json.loads(p.read_text())['pid'])/'cmdline'
    return f.read_bytes().decode().replace('\0',' ') if f.exists() else ''
assert t['status']=='gen8_collector_started' and 'ops/gen5_runtime.py' in cmd('process.json') and str(r) in cmd('process.json')
assert not cmd('publisher-process.json') and not cmd('watchdog-process.json') and not list((r/'failures').glob('*.json'))
heartbeat=json.loads((r/'heartbeat.json').read_text());assert heartbeat['epoch']>=json.loads((r/'process.json').read_text())['epoch'] and time.time()-heartbeat['epoch']<30
env=dict(os.environ,BRIDGE_ARENA_PYTHON=str(python),XDG_CACHE_HOME=str(w/'bridge-gen8-cache'),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',TF_NUM_INTRAOP_THREADS='1',TF_NUM_INTEROP_THREADS='1',TF_CPP_MIN_LOG_LEVEL='3')
def launch(name,args,log):
    with (r/log).open('a') as output:p=subprocess.Popen([str(python),'-u',*args],cwd=src,env=env,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
    write(r/name,dict(pid=p.pid,epoch=time.time()));return p.pid
with (w/'.bridge-gen8-transition.lock').open('a+') as guard:
    fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
    t['processes']['publisher']=launch('publisher-process.json',['ops/publish_gen5.py','--run',str(r),'--publication',str(pub)],'publisher.log')
    t['processes']['watchdog']=launch('watchdog-process.json',['ops/watch_gen5.py','--run',str(r),'--publication',str(pub),'--ben-state',str(w/'bridge-gen8-no-ben-state')],'watchdog.log')
    t.update(status='gen8_running_publication_pending',epoch=time.time());write(sp,t)
    for name in ('handoff.json','launch.json'):
        x=json.loads((r/name).read_text());x.update(status=t['status'],processes=t['processes'],epoch=time.time());write(r/name,x)
    dp=w/'bridge-new-stream.json';d=json.loads(dp.read_text());d['transition']['phase']=t['status'];write(dp,d)
    diag=json.loads((r/'preparation-diagnosis.json').read_text());diag['launcher_readiness']='Initial helper saw a stale prepared heartbeat immediately after spawning. Existing collector retained; fresh timestamp verified and publisher/watchdog started without restarting collection.';write(r/'preparation-diagnosis.json',diag)
print(json.dumps(dict(status=t['status'],processes=t['processes'],heartbeat=heartbeat)))
