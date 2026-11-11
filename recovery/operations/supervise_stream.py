"""Own this stream's collector, cache rotation, and dedicated publisher."""
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

BASE = Path(__file__).resolve().parent
CONFIG = json.loads((BASE / 'stream.json').read_text())
RUN = Path(CONFIG['run'])
RUNTIME = Path(CONFIG['runtime'])
sys.path.insert(0, str(RUNTIME))
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json


def writer_free():
    with (RUN / '.writer.lock').open('a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            return False


def launch(args, logfile, cwd):
    with (RUN / logfile).open('a') as log:
        return subprocess.Popen([sys.executable, '-u', *args], cwd=cwd,
            env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1',
                     TF_NUM_INTRAOP_THREADS='1', TF_NUM_INTEROP_THREADS='1',
                     TF_CPP_MIN_LOG_LEVEL='3', KERAS_HOME=str(BASE / 'keras-cache'),
                     MPLCONFIGDIR=str(BASE / 'matplotlib-cache'), XDG_CACHE_HOME=str(BASE / 'cache')),
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True)


def main():
    m = json.loads((RUN / 'manifest.json').read_text())
    verify_generation(RUN, m)
    preflight = json.loads((RUN / 'preflight.json').read_text())
    assert preflight['manifest'] == m['identity'] and len(preflight['deals']) >= 2
    with (RUN / '.watchdog.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert writer_free(), 'A collector already owns this run'
        atomic_json(RUN / 'watchdog-process.json', dict(pid=os.getpid(), epoch=time.time()))
        collector = publisher = None
        attempts = {}
        token = 'Self-play stream: drain for disposable DDS cache rotation.\n'
        while not (RUN / 'WATCHDOG_STOP').exists():
            state = json.loads((RUN / 'state.json').read_text())
            done = state['completed'] >= m['target']
            stopped = (RUN / 'STOP').exists()
            failures = list((RUN / 'failures').glob('*.json'))
            status = dict(epoch=time.time(), completed=state['completed'], target=m['target'],
                          manifest=m['identity'], collector='stopped', publisher='stopped',
                          workers=3, ben_workers=0, failures=len(failures))
            cache = RUN / 'dds-cache.sqlite'
            cache_bytes = sum(p.stat().st_size for p in RUN.glob('dds-cache.sqlite*'))
            if shutil.disk_usage(RUN).free < 3 * 1024**3 and not stopped:
                (RUN / 'STOP').write_text('Disk space guard; inspect storage before resuming.\n')
                stopped = True
            if cache_bytes > 2 * 1024**3 and not stopped and not done:
                (RUN / 'STOP').write_text(token)
                stopped = True
            alive = collector is not None and collector.poll() is None
            if stopped and (RUN / 'STOP').read_text() == token and not alive and writer_free():
                # Cache is a regenerable solver memo, never an episode or training label.
                for path in RUN.glob('dds-cache.sqlite*'):
                    path.unlink()
                atomic_json(RUN / 'last-cache-rotation.json', dict(epoch=time.time(),
                            completed=state['completed'], previous_bytes=cache_bytes))
                (RUN / 'STOP').unlink()
                stopped = False
            if alive:
                status['collector'] = 'draining' if stopped else 'running'
                status['collector_pid'] = collector.pid
            elif done:
                status['collector'] = 'complete'
            elif failures:
                status['collector'] = 'blocked-preserved-failure'
            elif not stopped:
                key = state['completed']
                attempts[key] = attempts.get(key, 0) + 1
                if attempts[key] > 3:
                    status['collector'] = 'blocked-repeated-loss-without-progress'
                elif not writer_free():
                    status['collector'] = 'locked-awaiting-inspection'
                else:
                    verify_generation(RUN, m)
                    collector = launch(['ops/gen5_runtime.py', '--run', str(RUN), '--workers', '3'],
                                       'collector.log', RUNTIME)
                    atomic_json(RUN / 'process.json', dict(pid=collector.pid, epoch=time.time()))
                    status.update(collector='starting', collector_pid=collector.pid)
            if not (RUN / 'PUBLISH_STOP').exists():
                if publisher is None or publisher.poll() is not None:
                    publisher = launch([str(BASE / 'publish_stream.py')], 'publisher.log', BASE)
                status.update(publisher='running', publisher_pid=publisher.pid)
            atomic_json(RUN / 'watchdog-status.json', status)
            if done and not alive:
                if publisher is not None:
                    publisher.wait()
                break
            time.sleep(10)


if __name__ == '__main__':
    main()
