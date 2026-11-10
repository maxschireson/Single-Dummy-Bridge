"""One-thread whole-board budget addendum; runs alongside the original pilot."""
import argparse,datetime,fcntl,json,os,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.selfplay import atomic_json
from scripts.report_effort_pilot import report

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();root=a.run.resolve()
    lock=(root/'budget-supervisor.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    plan=json.loads((root/'plan.json').read_text());deadline=datetime.datetime.fromisoformat(plan['deadline_utc']).timestamp()
    env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','TF_CPP_MIN_LOG_LEVEL':'3'}
    for kind,epochs in [('policy',2),('belief',6)]:
        out=root/'fits'/f'{kind}_budget'
        while time.time()<deadline:
            state=json.loads((out/'state.json').read_text()) if (out/'state.json').exists() else dict(completed_epochs=0)
            if state['completed_epochs']>=epochs:break
            with (out/'writer.lock').open('a+') as h:
                try:fcntl.flock(h,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:return
            atomic_json(root/'budget-status.json',dict(stage=kind,epoch=state['completed_epochs']+1,updated=time.time()))
            with (out/'pipeline.log').open('a',buffering=1) as log:
                script='scripts/train_effort_policy.py' if kind=='policy' else 'scripts/train_belief_lab.py'
                proc=subprocess.Popen([sys.executable,'-u',script,'--config',str(out/'config.json')],stdout=log,stderr=log,env=env)
                while True:
                    try:rc=proc.wait(timeout=10);break
                    except subprocess.TimeoutExpired:
                        if time.time()>deadline+120:
                            proc.terminate();proc.wait();return
                if rc:atomic_json(out/'error.json',dict(exit_code=rc,time=time.time()));return
                epoch=json.loads((out/'state.json').read_text())['completed_epochs']
                if kind=='belief':
                    rc=subprocess.call([sys.executable,'scripts/score_belief_joint.py','--model',str(out/f'epoch-{epoch}.npz'),'--data',plan['belief_base'],'--out',str(out/f'joint-{epoch}.json')],stdout=log,stderr=log,env=env)
                    if rc:return
            # The main pilot owns progress.md/comparison.json while active;
            # avoid concurrent report writers. The monitor refreshes both.
    atomic_json(root/'budget-status.json',dict(stage='complete' if time.time()<deadline else 'deadline_partial',updated=time.time()))

if __name__=='__main__':main()
