"""Live, two-worker pilot supervisor; exact writer locks and immutable stages."""
import argparse,concurrent.futures,datetime,fcntl,json,os,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.selfplay import atomic_json
from scripts.report_effort_pilot import report

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();root=a.run.resolve()
    lock=(root/'supervisor.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    plan=json.loads((root/'plan.json').read_text());deadline=datetime.datetime.fromisoformat(plan['deadline_utc']).timestamp()
    lab=Path('runs/belief-lab-20261110').resolve();jobs=json.loads((root/'jobs.json').read_text())
    none=root/'fits/belief_none';none.mkdir(exist_ok=True)
    if not (none/'config.json').exists():
        cfg=json.loads((lab/'fits/dense_added/config.json').read_text());cfg['threads']=2;atomic_json(none/'config.json',cfg)
    jobs=[dict(name=none.name,config=str(none/'config.json'))]+jobs
    for name in ('none','high','low','quantity'):
        out=root/'fits'/('policy_'+name);out.mkdir(exist_ok=True)
        if not (out/'config.json').exists():atomic_json(out/'config.json',dict(base=plan['policy_base'],parent=plan['policy_parent'],extra=None if name=='none' else str(root/'data'/name/'policy.npz'),seed=2026111029,epochs=2,lr=1e-5))
    env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','TF_CPP_MIN_LOG_LEVEL':'3'}
    def run(args,stage):
        if time.time()>=deadline:return False
        out=root/'fits'/stage.split(':')[-1]
        with (out/'writer.lock').open('a+') as h:
            try:fcntl.flock(h,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:return False
        with (out/'pipeline.log').open('a',buffering=1) as log:
            log.write(json.dumps(dict(started=time.time(),args=args))+'\n')
            proc=subprocess.Popen([sys.executable,'-u',*args],stdout=log,stderr=log,env=env)
            while True:
                try:rc=proc.wait(timeout=10);break
                except subprocess.TimeoutExpired:
                    atomic_json(out/'worker.json',dict(stage=stage,updated=time.time(),pid=proc.pid))
                    if time.time()>deadline+120:proc.terminate();proc.wait();return False
            if rc:atomic_json(out/'error.json',dict(stage=stage,exit_code=rc,time=time.time()))
            return rc==0
    # Two fits x two TF threads leaves four threads for the main research queue.
    # First fixed-epoch belief comparison is reported before policy work begins.
    for kind,epochs in [('belief',1),('policy',2),('belief',6)]:
        active=jobs if kind=='belief' else [dict(name='policy_'+n,config=str(root/'fits'/('policy_'+n)/'config.json')) for n in ('none','high','low','quantity')]
        for epoch in range(1,epochs+1):
            if time.time()>=deadline:break
            atomic_json(root/'status.json',dict(stage=kind,epoch=epoch,updated=time.time(),deadline=deadline))
            def one(job):
                out=Path(job['config']).parent;state=out/'state.json'
                if not state.exists() or json.loads(state.read_text())['completed_epochs']<epoch:
                    script='scripts/train_belief_lab.py' if kind=='belief' else 'scripts/train_effort_policy.py'
                    if not run([script,'--config',job['config']],'fit:'+job['name']):return False
                if kind=='belief':
                    return run(['scripts/score_belief_joint.py','--model',str(out/f'epoch-{epoch}.npz'),'--data',plan['belief_base'],'--out',str(out/f'joint-{epoch}.json')],'joint:'+job['name'])
                return True
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(one,active))
            report(root)
            if not all(results):atomic_json(root/'status.json',dict(stage='needs_recovery',kind=kind,epoch=epoch,updated=time.time()));return
            if kind=='policy':run(['scripts/evaluate_effort_policy_fresh.py','--run',str(root)],'fresh:policy_none')
    atomic_json(root/'status.json',dict(stage='complete' if time.time()<deadline else 'deadline_partial',updated=time.time(),promoted=False))

if __name__=='__main__':main()
