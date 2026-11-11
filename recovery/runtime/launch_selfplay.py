"""Locked supervisor for this additional fast-self-play cohort only."""
import fcntl,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
run=ROOT/'runs/fast-only-20261111'
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',TF_NUM_INTRAOP_THREADS='1',TF_NUM_INTEROP_THREADS='1',TF_CPP_MIN_LOG_LEVEL='3')
with (run/'.supervisor.lock').open('a+') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    m=json.loads((run/'manifest.json').read_text())
    assert m['pair_schedule']==['6-32~6-32']
    assert json.loads((run/'capture-equivalence.json').read_text())['status']=='passed'
    (run/'supervisor.json').write_text(json.dumps(dict(pid=os.getpid(),epoch=time.time(),workers=2,command='launch_selfplay.py')))
    while not (run/'STOP').exists():
        if list((run/'failures').glob('*.json')):sys.exit('Preserved failure requires inspection')
        if json.loads((run/'state.json').read_text()).get('complete'):break
        result=subprocess.run([sys.executable,'-u','ops/gen5_runtime.py','--run',str(run),'--workers','2'],cwd=ROOT,env=env)
        if result.returncode==0:break
        if list((run/'failures').glob('*.json')):sys.exit(result.returncode)
        time.sleep(10)
