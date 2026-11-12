import fcntl,json,os,subprocess,time
from pathlib import Path

work=Path('/workspace/work');sp=work/'bridge-gen8-transition-state.json';t=json.loads(sp.read_text());run=Path(t['new_run']);source=Path(t['new_source']);pub=Path(t['new_publication']);python=work/'bridge-venv/bin/python'
def write(p,v):
    tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(v,indent=2)+'\n');tmp.replace(p)
def alive(p):
    if not p.exists():return False
    f=Path('/proc')/str(json.loads(p.read_text())['pid'])/'cmdline'
    return f.exists() and bool(f.read_bytes())
assert t['status']=='gen8_validated_ready_to_launch'
m=json.loads((run/'manifest.json').read_text());v=json.loads((run/'validation.json').read_text());assert v['status']=='passed' and v['manifest']==m['identity']
old=Path(t['initial_descriptor']['run'])
assert all((old/n).exists() for n in ('STOP','WATCHDOG_STOP','PUBLISH_STOP'))
assert not any(alive(old/n) for n in ('process.json','watchdog-process.json','publisher-process.json'))
assert not list((run/'failures').glob('*.json')) and not any((run/n).exists() for n in ('STOP','WATCHDOG_STOP','PUBLISH_STOP'))
for name in ('process.json','watchdog-process.json','publisher-process.json'):assert not alive(run/name)
env=dict(os.environ,BRIDGE_ARENA_PYTHON=str(python),XDG_CACHE_HOME=str(work/'bridge-gen8-cache'),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',TF_NUM_INTRAOP_THREADS='1',TF_NUM_INTEROP_THREADS='1',TF_CPP_MIN_LOG_LEVEL='3')
def launch(name,args,log):
    with (run/log).open('a') as output:
        p=subprocess.Popen([str(python),'-u',*args],cwd=source,env=env,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
    write(run/name,dict(pid=p.pid,epoch=time.time()));return p.pid
with (work/'.bridge-gen8-transition.lock').open('a+') as guard:
    fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
    collector=launch('process.json',['ops/gen5_runtime.py','--run',str(run),'--workers','3'],'supervisor.log')
    deadline=time.monotonic()+120
    while not (run/'heartbeat.json').exists():
        if not alive(run/'process.json') or time.monotonic()>deadline:raise RuntimeError('Collector did not establish a fresh heartbeat')
        time.sleep(1)
    heartbeat=json.loads((run/'heartbeat.json').read_text());assert time.time()-heartbeat['epoch']<30
    publisher=launch('publisher-process.json',['ops/publish_gen5.py','--run',str(run),'--publication',str(pub)],'publisher.log')
    watchdog=launch('watchdog-process.json',['ops/watch_gen5.py','--run',str(run),'--publication',str(pub),'--ben-state',str(work/'bridge-gen8-no-ben-state')],'watchdog.log')
    t.update(status='gen8_running_publication_pending',processes=dict(collector=collector,publisher=publisher,watchdog=watchdog),epoch=time.time());write(sp,t)
    handoff=json.loads((run/'handoff.json').read_text());handoff.update(status=t['status'],processes=t['processes'],epoch=time.time());write(run/'handoff.json',handoff);write(run/'launch.json',handoff)
    dp=work/'bridge-new-stream.json';d=json.loads(dp.read_text());d['transition']['phase']=t['status'];write(dp,d)
print(json.dumps(dict(status=t['status'],processes=t['processes'],heartbeat=heartbeat)),flush=True)
