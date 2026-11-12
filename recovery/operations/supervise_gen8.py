"""Supervise only this owned Gen8 cohort; the retired Gen7.1 gate is disabled."""
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
from bridge_harness.loop_registry import sha
from bridge_harness.selfplay import atomic_json


def validate_launch(m, preflight, capture):
    assert m.get('effective_generation') == 8 and m.get('systems') and m.get('gen8')
    assert not m.get('gen71_gate') and m['collection_control']['gen71_comparison_gate_enabled'] is False
    assert preflight['manifest'] == capture['manifest'] == m['identity']
    assert all(sum(row['pair'] == pair for row in preflight['deals']) >= 2 for pair in m['pair_weights'])
    assert m['evaluation_exclusions']['families'] == 34092
    assert capture['gap_forks'] > 0 and capture['guess_size'] > 0 and capture['best_share'] > 0
    assert capture['replay_score_and_systems_verified'] is True


def free(name):
    with (RUN / name).open('a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            return False


def launch(args, logname, cwd):
    with (RUN / logname).open('a') as log:
        return subprocess.Popen([sys.executable, '-u', *args], cwd=cwd,
            env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
                BRIDGE_DDS_CACHE=str(RUN / 'dds-cache.sqlite'),
                TF_NUM_INTRAOP_THREADS='1', TF_NUM_INTEROP_THREADS='1', TF_CPP_MIN_LOG_LEVEL='3',
                KERAS_HOME=str(BASE / 'keras-cache'), MPLCONFIGDIR=str(BASE / 'matplotlib-cache'),
                XDG_CACHE_HOME=str(BASE / 'cache')),
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)


def main():
    m = json.loads((RUN / 'manifest.json').read_text())
    verify_generation(RUN, m)
    assert m['source_commit'] == CONFIG['source_commit']
    assert sha(RUN / m['evaluation_exclusions']['path']) == m['evaluation_exclusions']['sha256']
    validate_launch(m, json.loads((RUN / 'preflight.json').read_text()),
                    json.loads((RUN / 'preflight-capture.json').read_text()))
    with (RUN / '.watchdog.lock').open('a+') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert free('.writer.lock') and free('.publisher.lock'), 'An existing owner must be inspected, not taken over'
        atomic_json(RUN / 'watchdog-process.json', dict(pid=os.getpid(), epoch=time.time()))
        collector = publisher = None
        launched = cache_resume = False
        token = 'Gen8: intentional drain for disposable DDS cache rotation.\n'
        while not (RUN / 'WATCHDOG_STOP').exists():
            state = json.loads((RUN / 'state.json').read_text())
            done = state['completed'] >= m['target']
            failures = list((RUN / 'failures').glob('*.json'))
            alive = collector is not None and collector.poll() is None
            stop = RUN / 'STOP'
            cache_bytes = sum(path.stat().st_size for path in RUN.glob('dds-cache.sqlite*'))
            if shutil.disk_usage(RUN).free < 3 * 1024**3 and not stop.exists():
                stop.write_text('Disk space guard; preserve records and inspect storage.\n')
            if cache_bytes > 2 * 1024**3 and not stop.exists() and not done:
                stop.write_text(token)
            if stop.exists() and stop.read_text() == token and not alive and free('.writer.lock'):
                for path in RUN.glob('dds-cache.sqlite*'):
                    path.unlink()
                atomic_json(RUN / 'last-cache-rotation.json', dict(epoch=time.time(),
                    completed=state['completed'], previous_bytes=cache_bytes))
                stop.unlink()
                cache_resume = True
            status = dict(epoch=time.time(), completed=state['completed'], target=m['target'],
                manifest=m['identity'], workers=3, ben_workers=0, failures=len(failures),
                collector='stopped', publisher='stopped', gen71_comparison_gate_enabled=False)
            if alive:
                status.update(collector='draining' if stop.exists() else 'running', collector_pid=collector.pid)
            elif done:
                status['collector'] = 'source-budget-complete'
            elif stop.exists():
                status['collector'] = 'intentionally-stopped'
            elif failures:
                status['collector'] = 'blocked-preserved-failure'
            elif not launched or cache_resume:
                verify_generation(RUN, m)
                assert free('.writer.lock')
                collector = launch(['ops/gen5_runtime.py', '--run', str(RUN), '--workers', '3'], 'collector.log', RUNTIME)
                atomic_json(RUN / 'process.json', dict(pid=collector.pid, epoch=time.time()))
                status.update(collector='starting', collector_pid=collector.pid)
                launched = True
                cache_resume = False
            else:
                status['collector'] = 'blocked-unexpected-exit'
                stop.write_text('Collector exited unexpectedly; diagnose logs and preserve failures before any restart.\n')
                atomic_json(RUN / 'supervisor-failure.json', dict(epoch=time.time(),
                    returncode=collector.returncode if collector else None, completed=state['completed']))
            published = json.loads((RUN / 'publisher-status.json').read_text()) if (RUN / 'publisher-status.json').exists() else {}
            publication_done = done and published.get('status') == 'published' and published.get('completed') == m['target']
            if not (RUN / 'PUBLISH_STOP').exists():
                if publisher is None or publisher.poll() is not None:
                    if not publication_done:
                        publisher = launch([str(BASE / 'publish_stream.py')], 'publisher.log', BASE)
                status.update(publisher='source-budget-complete' if publication_done else 'running',
                              publisher_pid=publisher.pid if publisher else None)
            atomic_json(RUN / 'watchdog-status.json', status)
            if done and publication_done and not alive:
                break
            time.sleep(10)


if __name__ == '__main__':
    main()
