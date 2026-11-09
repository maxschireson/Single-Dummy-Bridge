"""Resume the frozen clean dense-belief pipeline through its final export."""
import argparse, fcntl, json, os, subprocess, sys, time
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);a=p.parse_args()
    cfg=json.loads(a.config.read_text());root=Path(cfg['repo']);out=root/cfg['out'];out.mkdir(parents=True,exist_ok=True)
    lock=(out/'pipeline.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','TF_CPP_MIN_LOG_LEVEL':'2'}
    def run(script,args):
        with (out/'pipeline.log').open('a',buffering=1) as log:
            log.write(json.dumps(dict(script=script,started=time.time()))+'\n')
            subprocess.run([cfg['python'],'-u',script,*args],cwd=root,env=env,stdout=log,stderr=log,check=True)
    if not (out/'dataset.json').exists():
        args=[]
        for k in ('base','parent-partition','parent-checkpoint','old-screen','clean-sources','out'):
            args += ['--'+k,cfg[k]]
        args+=['--workers',str(cfg.get('workers',2))]
        run('scripts/prepare_impactful_belief.py',args)
    if not (out/'fit/result.json').exists():
        run('scripts/train_impactful_belief.py',['--data',str(out),'--out',str(out/'fit'),'--threads',str(cfg.get('threads',2))])
    print((out/'status.json').read_text(),flush=True)

if __name__=='__main__':main()
