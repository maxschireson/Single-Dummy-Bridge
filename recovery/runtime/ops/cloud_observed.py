"""Observe the pinned cloud collector without modifying its play implementation."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ops.diagnostic_supervisor import DiagnosticPool, Recorder, memory_snapshot


def main():
    run = Path(sys.argv[2]).resolve()
    record = Recorder(run, 'cloud-' + sys.argv[1])
    record.emit('start', resources=memory_snapshot())
    try:
        if sys.argv[1] == 'collect':
            import ops.gen5_runtime as runtime
            DiagnosticPool.run = run
            runtime.ProcessPoolExecutor = DiagnosticPool
            runtime.run(run, 3)
        else:
            import ops.supervise_cloud_selfplay as supervisor
            original = supervisor.subprocess.Popen

            def launch(args, *a, **kw):
                if len(args) > 2 and args[2] == 'ops/gen5_runtime.py':
                    args = [sys.executable, '-u', str(Path(__file__).resolve()),
                            'collect', str(run)]
                record.emit('child-launch', resources=memory_snapshot())
                return original(args, *a, **kw)

            supervisor.subprocess.Popen = launch
            supervisor.supervise(run)
    except BaseException as exc:
        record.emit('error', error=repr(exc), resources=memory_snapshot())
        raise
    finally:
        record.emit('exit', resources=memory_snapshot())


if __name__ == '__main__':
    os.environ['PYTHONFAULTHANDLER'] = '1'
    main()
