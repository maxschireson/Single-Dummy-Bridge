"""Supervise this producer's frozen Gen7 run, publication, and pooled Gen7.1 gate."""
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
RUN = Path(CONFIG['run']); RUNTIME = Path(CONFIG['runtime'])
sys.path.insert(0, str(RUNTIME))
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json
from gen71_gate import update as update_fleet


def free(name):
    with (RUN / name).open('a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB); return True
        except BlockingIOError:
            return False


def launch(args, logname, cwd):
    with (RUN / logname).open('a') as log:
        return subprocess.Popen([sys.executable, '-u', *args], cwd=cwd,
            env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
                TF_NUM_INTRAOP_THREADS='1', TF_NUM_INTEROP_THREADS='1', TF_CPP_MIN_LOG_LEVEL='3',
                KERAS_HOME=str(BASE / 'keras-cache'), MPLCONFIGDIR=str(BASE / 'matplotlib-cache'),
                XDG_CACHE_HOME=str(BASE / 'cache')),
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)


def main():
    m = json.loads((RUN / 'manifest.json').read_text()); verify_generation(RUN, m)
    preflight = json.loads((RUN / 'preflight.json').read_text())
    assert preflight['manifest'] == m['identity']
    assert all(sum(d['pair'] == p for d in preflight['deals']) >= 2 for p in m['pair_weights'])
    if m.get('gap_fork', {}).get('per_band', 0):
        assert sum(d.get('gap_forks', 0) for d in preflight['deals']) > 0, 'Required gap capture was not exercised in preflight'
    with (RUN / '.watchdog.lock').open('a+') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert free('.writer.lock'), 'An existing writer owns the run'
        atomic_json(RUN / 'watchdog-process.json', dict(pid=os.getpid(), epoch=time.time()))
        collector = publisher = None; launched = False; cache_resume = False
        next_fleet = 0; last_fleet = time.time(); fleet_ready = False
        token = 'Gen7.1: intentional drain for disposable DDS cache rotation.\n'
        while not (RUN / 'WATCHDOG_STOP').exists():
            if time.time() >= next_fleet:
                try:
                    fleet = update_fleet(RUN, RUNTIME)
                    if fleet['errors']:
                        raise RuntimeError('Incomplete Gen7.1 gate snapshots: ' + repr(fleet['errors']))
                    last_fleet = time.time(); fleet_ready = True
                except Exception as exc:
                    atomic_json(RUN / 'gen71-gate-error.json', dict(epoch=time.time(), error=repr(exc)))
                next_fleet = time.time() + 60
            state = json.loads((RUN / 'state.json').read_text()); done = state['completed'] >= m['target']
            failures = list((RUN / 'failures').glob('*.json'))
            alive = collector is not None and collector.poll() is None
            stop = RUN / 'STOP'; cache_bytes = sum(p.stat().st_size for p in RUN.glob('dds-cache.sqlite*'))
            if shutil.disk_usage(RUN).free < 3 * 1024**3 and not stop.exists():
                stop.write_text('Disk space guard; preserve records and inspect storage.\n')
            if time.time() - last_fleet > 600 and not stop.exists():
                stop.write_text('Gen7.1 pooled gate unavailable for 10 minutes; inspect before resuming.\n')
            if cache_bytes > 2 * 1024**3 and not stop.exists() and not done:
                stop.write_text(token)
            if stop.exists() and stop.read_text() == token and not alive and free('.writer.lock'):
                for path in RUN.glob('dds-cache.sqlite*'):
                    path.unlink()
                atomic_json(RUN / 'last-cache-rotation.json', dict(epoch=time.time(),
                    completed=state['completed'], previous_bytes=cache_bytes))
                stop.unlink(); cache_resume = True
            status = dict(epoch=time.time(), completed=state['completed'], target=m['target'],
                manifest=m['identity'], workers=3, ben_workers=0, failures=len(failures),
                collector='stopped', publisher='stopped', last_fleet_check=last_fleet)
            if alive:
                status.update(collector='draining' if stop.exists() else 'running', collector_pid=collector.pid)
            elif done:
                status['collector'] = 'source-budget-complete'
            elif stop.exists():
                status['collector'] = 'intentionally-stopped'
            elif failures:
                status['collector'] = 'blocked-preserved-failure'
            elif not fleet_ready:
                status['collector'] = 'waiting-for-first-fleet-check'
            elif not launched or cache_resume:
                verify_generation(RUN, m)
                assert free('.writer.lock')
                collector = launch(['ops/gen5_runtime.py', '--run', str(RUN), '--workers', '3'],
                                   'collector.log', RUNTIME)
                atomic_json(RUN / 'process.json', dict(pid=collector.pid, epoch=time.time()))
                status.update(collector='starting', collector_pid=collector.pid)
                launched = True; cache_resume = False
            else:
                status['collector'] = 'blocked-unexpected-exit'
                stop.write_text('Collector exited unexpectedly; diagnose logs and preserve failures before any restart.\n')
                atomic_json(RUN / 'supervisor-failure.json', dict(epoch=time.time(),
                    returncode=collector.returncode if collector else None, completed=state['completed']))
            if not (RUN / 'PUBLISH_STOP').exists():
                if publisher is None or publisher.poll() is not None:
                    publisher = launch([str(BASE / 'publish_stream.py')], 'publisher.log', BASE)
                status.update(publisher='running', publisher_pid=publisher.pid)
            atomic_json(RUN / 'watchdog-status.json', status)
            time.sleep(10)


if __name__ == '__main__':
    main()
