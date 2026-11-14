"""Recover the frozen Gen5 collector/publisher and cap its disposable DDS cache."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
DEFAULT_PYTHON=Path('/workspace/work/ben-venv/bin/python')
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json

def alive(path,script):
    try:return script.encode() in Path(f"/proc/{json.loads(path.read_text())['pid']}/cmdline").read_bytes()
    except (OSError,ValueError,KeyError):return False

def free(path):
    with path.open('a+') as f:
        try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);return True
        except BlockingIOError:return False

def launch(root,name,args,log,cwd=ROOT):
    executable=os.environ.get('BRIDGE_ARENA_PYTHON') or (str(DEFAULT_PYTHON) if DEFAULT_PYTHON.is_file() else sys.executable)
    with (root/log).open('a') as output:
        child=subprocess.Popen([executable,'-u',*args],cwd=cwd,
            env=dict(os.environ,BRIDGE_ARENA_PYTHON=executable,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',TF_NUM_INTRAOP_THREADS='1',TF_NUM_INTEROP_THREADS='1',XDG_CACHE_HOME='/workspace/work/gen5-cache',TF_CPP_MIN_LOG_LEVEL='3'),
            stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
    atomic_json(root/name,dict(pid=child.pid,epoch=time.time()));return child.pid

def ben_ready(port=8087):
    try:
        with socket.create_connection(('127.0.0.1',port),timeout=1):return True
    except OSError:return False

def ben_services(m,run):
    services={}
    for spec in m['bots'].values():
        if spec.get('engine')!='ben':continue
        url=urlparse(spec['url'])
        if url.hostname!='127.0.0.1' or not url.port:raise ValueError('BEN watchdog expects a local service with an explicit port')
        config=run/spec['config']
        if url.port in services and services[url.port]!=config:raise ValueError('Conflicting BEN configs on one port')
        services[url.port]=config
    return services

def main(run,pub,ben_dir=Path('/workspace/work/ben-next-round'),ben_state=Path('/workspace/work/round5')):
    ben_state.mkdir(parents=True,exist_ok=True)
    with (run/'.watchdog.lock').open('a+') as guard:
        fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB);attempts={}
        token='GEN5_DDS_CACHE_ROTATION\n'
        while not (run/'WATCHDOG_STOP').exists():
            status=dict(epoch=time.time(),collector='running',publisher='running');stop=run/'STOP'
            try:
                m=json.loads((run/'manifest.json').read_text());s=json.loads((run/'state.json').read_text());complete=s['completed']>=m['target']
                services=ben_services(m,run)
                for port,config in services.items():
                    marker='ben-process.json' if port==8087 else f'ben-{port}-process.json'
                    if not alive(ben_state/marker,'gameapi.py'):
                        status[f'ben_{port}_pid']=launch(ben_state,marker,['src/gameapi.py','--config',str(config),'--port',str(port),'--host','127.0.0.1','--record','false'],f'ben-{port}-server.log',cwd=ben_dir)
                ready=all(ben_ready(port) for port in services);status['ben']='ready' if ready else 'warming'
                cache=run/'dds-cache.sqlite';size=cache.stat().st_size if cache.exists() else 0
                if size>2*1024**3 and not stop.exists():stop.write_text(token);status['collector']='draining-for-cache-rotation'
                if stop.exists() and stop.read_text()==token and not alive(run/'process.json','gen5_runtime.py') and free(run/'.writer.lock'):
                    # Workers have drained before deleting derived memoized answers.
                    with sqlite3.connect(cache) as db:
                        db.execute('DELETE FROM positions');db.commit();db.execute('PRAGMA wal_checkpoint(TRUNCATE)');db.execute('VACUUM')
                    atomic_json(run/'last-cache-rotation.json',dict(epoch=time.time(),previous_bytes=size,completed=s['completed']))
                    if stop.read_text()==token:stop.unlink()
                if shutil.disk_usage(run).free<3*1024**3:
                    if not stop.exists():stop.write_text('Disk space guard: preserve completed records and inspect storage.\n')
                    status['collector']='disk-space-guard'
                if stop.exists():status['collector']='intentionally-stopped-or-draining'
                elif complete:status['collector']='complete'
                elif not ready:status['collector']='waiting-for-ben'
                elif not alive(run/'process.json','gen5_runtime.py') and free(run/'.writer.lock'):
                    verify_generation(run,m);failures=list((run/'failures').glob('*.json'))
                    if failures:status['collector']='blocked-preserved-failure'
                    else:
                        key=s['completed'];attempts[key]=attempts.get(key,0)+1
                        if attempts[key]>3:status['collector']='blocked-repeated-loss'
                        else:status['collector_pid']=launch(run,'process.json',['ops/gen5_runtime.py','--run',str(run),'--workers','3'],'supervisor.log')
                published=json.loads((pub/'arena/data.json').read_text())['completed'] if (pub/'arena/data.json').exists() else 0
                if (not complete or published<m['target']) and not alive(run/'publisher-process.json','publish_gen5.py'):
                    status['publisher_pid']=launch(run,'publisher-process.json',['ops/publish_gen5.py','--run',str(run),'--publication',str(pub)],'publisher.log')
                if complete:status['collector']='complete'
            except Exception as e:status['error']=str(e)
            atomic_json(run/'watchdog-status.json',status);time.sleep(60)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--publication',type=Path,required=True)
    p.add_argument('--ben-dir',type=Path,default=Path('/workspace/work/ben-next-round'));p.add_argument('--ben-state',type=Path,default=Path('/workspace/work/round5'))
    a=p.parse_args();main(a.run.resolve(),a.publication.resolve(),a.ben_dir.resolve(),a.ben_state.resolve())
