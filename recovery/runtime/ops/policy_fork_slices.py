"""Finish a fixed fork block in bounded subprocess slices, then fit its IMP head."""
import argparse
import fcntl
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,default=ROOT/'runs/random-policy-forks-v1')
    p.add_argument('--fit',type=Path,default=ROOT/'runs/fork-imp-head-v1')
    p.add_argument('--seconds',type=float,default=180);a=p.parse_args();a.run=a.run.resolve()
    with (a.run/'.slice-supervisor.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        while not (a.run/'STOP').exists():
            state=json.loads((a.run/'state.json').read_text()) if (a.run/'state.json').exists() else {}
            if state.get('complete'):break
            args=[sys.executable,'scripts/collect_policy_forks.py','--root',str(a.run),'--corpus',str(a.run/'corpus.jsonl'),
                '--belief',str(a.run/'artifacts/belief.npz'),'--bootstrap',str(a.run/'artifacts/bootstrap.npz'),
                '--incumbent',str(a.run/'artifacts/incumbent.npz'),'--seconds',str(a.seconds)]
            with (a.run/'collector.log').open('a') as log:
                subprocess.run(args,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
            current=json.loads((a.run/'state.json').read_text())
            print(json.dumps(current),flush=True)
            if current['boards']<=state.get('boards',0):raise RuntimeError('No progress; inspect collector log')
        if (a.run/'STOP').exists():return
        if not a.fit.exists():
            subprocess.run([sys.executable,'scripts/train_fork_policy.py','--run',str(a.run),
                '--out',str(a.fit),'--bootstrap',str(a.run/'artifacts/bootstrap.npz')],cwd=ROOT,check=True)


if __name__=='__main__':main()
