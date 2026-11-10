"""Sequential bounded workers; frozen two-arm comparison and automatic report."""
import argparse,fcntl,json,os,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.belief_capacity import sha
from bridge_harness.selfplay import atomic_json

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--data',type=Path,required=True)
    p.add_argument('--parent',type=Path,required=True);p.add_argument('--epochs',type=int,default=3);p.add_argument('--smoke-shards',type=int,default=0)
    a=p.parse_args();a.run.mkdir(parents=True,exist_ok=True)
    lock=(a.run/'pipeline.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    cfg=dict(schema='residual-belief-matched-v1',data=str(a.data.resolve()),parent=str(a.parent.resolve()),
        parent_sha256=sha(a.parent),dataset_sha256=sha(a.data/'dataset.json'),epochs=a.epochs,smoke_shards=a.smoke_shards,
        architecture=dict(width=64,heads=2,blocks=1),seed=2026111011,batch_size=128,learning_rate=1e-4,
        code_sha256={n:sha(n) for n in ['scripts/train_residual_belief.py','scripts/residual_belief_common.py','bridge_harness/residual_attention_belief.py','bridge_harness/belief_capacity.py','scripts/train_belief_factorial.py']},
        primary='Paired attention-minus-dense at fixed final epoch',secondary='Best frozen composite including epoch zero',
        reserved_test_evaluated=False,promoted=False)
    cp=a.run/'experiment.json'
    if cp.exists() and json.loads(cp.read_text())!=cfg:raise ValueError('Pipeline config changed')
    atomic_json(cp,cfg);completed=[]
    for mode in ['dense','attention']:
        while not (a.run/mode/'result.json').exists():
            cmd=[sys.executable,'-u','scripts/train_residual_belief.py','--data',str(a.data),'--parent',str(a.parent),
                '--out',str(a.run/mode),'--mode',mode,'--epochs',str(a.epochs),'--smoke-shards',str(a.smoke_shards)]
            with (a.run/'pipeline.log').open('a',buffering=1) as log:
                log.write(json.dumps(dict(mode=mode,started=time.time()))+'\n')
                proc=subprocess.Popen(cmd,stdout=log,stderr=log,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
                while True:
                    atomic_json(a.run/'status.json',dict(stage='training',active=mode,completed=completed,updated=time.time()))
                    try:code=proc.wait(timeout=10);break
                    except subprocess.TimeoutExpired:pass
                log.write(json.dumps(dict(mode=mode,exit_code=code,finished=time.time()))+'\n')
            if code:
                fp=a.run/(mode+'-interruptions.json');d=json.loads(fp.read_text()) if fp.exists() else dict(count=0)
                d.update(count=d['count']+1,exit_code=code,updated=time.time());atomic_json(fp,d)
                if code==-9 and d['count']<=5:continue
                atomic_json(a.run/'status.json',dict(stage='failed',active=mode,exit_code=code,updated=time.time()))
                raise subprocess.CalledProcessError(code,cmd)
        completed.append(mode)
    subprocess.run([sys.executable,'scripts/report_residual_belief.py','--run',str(a.run)],check=True)
    atomic_json(a.run/'status.json',dict(stage='complete',completed=completed,updated=time.time(),promoted=False,reserved_test_evaluated=False))

if __name__=='__main__':main()
