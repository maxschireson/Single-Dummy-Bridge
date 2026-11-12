import sys,os,signal,time,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ops.independent_workers import IndependentWorkers

def flaky(flag):
    p=Path(flag)
    if not p.exists():p.write_text('once');os.kill(os.getpid(),signal.SIGKILL)
    return 42

def healthy():
    time.sleep(1);return ('healthy',os.getpid())

def bad():raise ValueError('deliberate application failure')

if __name__=='__main__':
    with tempfile.TemporaryDirectory() as d:
        IndependentWorkers.run=d
        with IndependentWorkers(2) as pool:
            a=pool.submit(flaky,d+'/flag');b=pool.submit(healthy)
            assert a.result(timeout=20)==42
            assert b.result(timeout=20)[0]=='healthy'
            try:pool.submit(bad).result(timeout=20)
            except RuntimeError as e:assert 'deliberate application failure' in str(e)
            else:raise AssertionError('Application error was swallowed')
        import json
        events=[json.loads(l) for f in (Path(d)/'diagnostics').glob('independent*') for l in f.read_text().splitlines()]
        assert sum(e['event']=='retry-crashed-board' for e in events)==1
        print('PASS: killed worker retried, healthy peer finished, application error propagated')
