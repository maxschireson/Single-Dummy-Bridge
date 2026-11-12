"""Single-worker operational wrapper; frozen play source remains unchanged."""
from pathlib import Path
import fcntl
import sys

ROOT = Path('/workspace/scratch/f846a051cf69')
sys.path.insert(0, str(ROOT / 'gen7-cloud-source'))

def main():
    run = ROOT / 'gen7-phase1-cloud-v2-run'
    with (run / '.watchdog.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if any((run / name).exists() for name in ('STOP', 'WATCHDOG_STOP')):
            raise RuntimeError('Stop marker present')
        if list((run / 'failures').glob('*.json')):
            raise RuntimeError('Preserved failure requires inspection')
        from ops.diagnostic_supervisor import DiagnosticPool, Recorder, memory_snapshot
        from ops import gen5_runtime as runtime
        record = Recorder(run, 'cloud-gen7')
        record.emit('start', workers=1, resources=memory_snapshot())
        DiagnosticPool.run = run
        runtime.ProcessPoolExecutor = DiagnosticPool
        try:
            runtime.run(run, 1)
        except BaseException as exc:
            record.emit('error', error=repr(exc), resources=memory_snapshot())
            raise
        finally:
            record.emit('exit', resources=memory_snapshot())

if __name__ == '__main__':
    main()
