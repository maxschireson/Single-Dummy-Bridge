"""Local recovery watchdog for this arena's collector and feed publisher."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from bridge_harness.improvement import read
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json
from ops.watch_direct_arena import lock_state

def alive(run,name,script):
    try:
        pid=read(run/name)['pid']
        return script.encode() in Path(f'/proc/{pid}/cmdline').read_bytes()
    except (OSError,KeyError,ValueError):return False

def launch(run,name,args,log):
    with (run/log).open('a') as output:
        p=subprocess.Popen([sys.executable,'-u',*args],cwd=ROOT,
            env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'),
            stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
    atomic_json(run/name,dict(pid=p.pid,epoch=time.time(),workers=4))
    return p.pid

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True)
    p.add_argument('--publication',type=Path,required=True);p.add_argument('--diagnostic',type=Path,required=True)
    a=p.parse_args();run=a.run.resolve();publication=a.publication.resolve()
    with (run/'.watchdog.lock').open('a+') as guard:
        fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
        attempts={}
        while not (run/'WATCHDOG_STOP').exists():
            state=dict(epoch=time.time(),collector='running',publisher='running')
            try:
                m=read(run/'manifest.json');current=read(run/'state.json')
                complete=current['completed']>=m['target']
                stopped=(run/'STOP').exists()
                if stopped:state['collector']='intentionally-stopped'
                elif complete:state['collector']='complete'
                elif not alive(run,'process.json','gen4_mix.py'):
                    if any(lock_state(run/n)!='free' for n in ('.supervisor.lock','.writer.lock')):
                        state['collector']='locked-awaiting-inspection'
                    elif list((run/'failures').glob('*.json')):
                        state['collector']='blocked-preserved-failures'
                    else:
                        verify_generation(run,m)
                        key=current['completed'];attempts[key]=attempts.get(key,0)+1
                        if attempts[key]>3:state['collector']='blocked-repeated-loss-without-progress'
                        else:
                            subprocess.run([sys.executable,'ops/gen4_mix.py','audit','--run',str(run)],cwd=ROOT,check=True,capture_output=True)
                            state['collector_pid']=launch(run,'process.json',['ops/gen4_mix.py','run','--run',str(run),'--workers','4'],'supervisor.log')
                published=read(publication/'arena/data.json')['completed']
                if not alive(run,'publisher-process.json','publish_component_mix.py') and not (complete and published>=m['target']):
                    state['publisher_pid']=launch(run,'publisher-process.json',['ops/publish_component_mix.py','--run',str(run),'--publication',str(publication),'--diagnostic',str(a.diagnostic)],'publisher.log')
                if complete and published>=m['target']:
                    state.update(collector='complete',publisher='complete');atomic_json(run/'watchdog-status.json',state);return
            except Exception as e:state['error']=str(e)
            atomic_json(run/'watchdog-status.json',state)
            time.sleep(60)

if __name__=='__main__':main()
