"""Fixed-data seed replication; separate outputs, policy first, no test access."""
import argparse,concurrent.futures,datetime,fcntl,json,os,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.selfplay import atomic_json

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);a=ap.parse_args();root=a.run.resolve();root.mkdir(parents=True,exist_ok=True)
    lock=(root/'supervisor.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    plan=json.loads((root/'plan.json').read_text());deadline=datetime.datetime.fromisoformat(plan['deadline_utc']).timestamp()
    env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','TF_CPP_MIN_LOG_LEVEL':'3'}
    def one(job):
        out=Path(job['config']).parent;cfg=json.loads(Path(job['config']).read_text())
        with (out/'writer.lock').open('a+') as h:
            try:fcntl.flock(h,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:return False
        for epoch in range(1,cfg['epochs']+1):
            if time.time()>=deadline:return False
            state=json.loads((out/'state.json').read_text()) if (out/'state.json').exists() else {'completed_epochs':0}
            commands=[]
            if state['completed_epochs']<epoch:
                script='scripts/train_effort_policy.py' if job['kind']=='policy' else 'scripts/train_belief_lab.py'
                commands.append([script,'--config',job['config']])
            if job['kind']=='belief' and not (out/f'joint-{epoch}.json').exists():
                commands.append(['scripts/score_belief_joint.py','--model',str(out/f'epoch-{epoch}.npz'),'--data',plan['belief_base'],'--out',str(out/f'joint-{epoch}.json')])
            for command in commands:
                with (out/'pipeline.log').open('a',buffering=1) as log:
                    proc=subprocess.Popen([sys.executable,'-u',*command],stdout=log,stderr=log,env=env)
                    while True:
                        try:rc=proc.wait(timeout=10);break
                        except subprocess.TimeoutExpired:
                            atomic_json(out/'worker.json',dict(pid=proc.pid,epoch=epoch,updated=time.time()))
                            if time.time()>deadline+120:proc.terminate();proc.wait();return False
                    if rc:atomic_json(out/'error.json',dict(exit_code=rc,time=time.time()));return False
        return True
    for kind in ['policy','belief']:
        atomic_json(root/'status.json',dict(stage=kind,updated=time.time()))
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(one,[j for j in plan['jobs'] if j['kind']==kind]))
        if not all(results):atomic_json(root/'status.json',dict(stage='partial',kind=kind,updated=time.time()));return
    atomic_json(root/'status.json',dict(stage='complete',updated=time.time(),promoted=False))
if __name__=='__main__':main()
