"""Publish receipt-consistent, resumable snapshots of this stream only."""
import argparse
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
OUT = Path(CONFIG['publication'])
sys.path.insert(0, str(RUNTIME))
from bridge_harness.loop_registry import sha
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json
from ops.export_gen5 import export
from ops.gen5_runtime import state


def git(*args):
    return subprocess.run(['git', '-C', str(OUT), *args], check=True,
                          capture_output=True, text=True, timeout=120).stdout.strip()


def copy_file(source, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)


def publish():
    m = json.loads((RUN / 'manifest.json').read_text())
    verify_generation(RUN, m)
    if not (RUN / 'preflight.json').exists():
        raise RuntimeError('Production publication requires the completed preflight')
    recovery = OUT / 'recovery'
    recovery.mkdir(parents=True, exist_ok=True)
    for name in ('manifest.json', 'corpus.jsonl', 'plan.json', 'preflight.json',
                 'artifact-source-manifest.json', 'runtime-requirements.txt',
                 'environment.json', 'launch.json', 'production-validation.json',
                 'gen7-capture-report.json', 'gen7-capture-inputs.json', 'gen7-capture-monitor.json',
                 'source-indices.json', 'ancestor-source-indices.json', 'source-completed-inventory.json', 'source-manifest.json',
                 'actor-source-manifest.json', 'phase1-global-progress.json', 'phase1-seen-families.json',
                 'phase1-stop.json', 'phase1-guard-error.json', 'supervisor-failure.json',
                 'gen71-gate-progress.json', 'gen71-gate-inventory.json', 'gen71-gate-stop.json', 'gen71-gate-error.json',
                 'validation.json', 'gen7-alpha-report.json', 'browser-preview.json', 'browser-live.json',
                 'RECOVERY.txt', 'STOP', 'WATCHDOG_STOP'):
        if (RUN / name).exists():
            copy_file(RUN / name, recovery / name)
    for folder in ('artifacts', 'assets'):
        for path in (RUN / folder).rglob('*'):
            if path.is_file() and not (recovery / folder / path.relative_to(RUN / folder)).exists():
                copy_file(path, recovery / folder / path.relative_to(RUN / folder))
    for folder in ('failures', 'resolved-failures'):
        for path in (RUN / folder).glob('*.json'):
            copy_file(path, recovery / folder / path.name)
    for folder in ('episodes', 'receipts', 'failures'):
        (recovery / folder).mkdir(exist_ok=True)
    rows = []
    # Atomic receipts are the commit markers; freeze the list before reading episodes.
    for receipt_path in sorted((RUN / 'receipts').glob('*.json')):
        receipt_bytes = receipt_path.read_bytes()
        receipt = json.loads(receipt_bytes)
        assert receipt['manifest_identity'] == m['identity']
        episode = RUN / 'episodes' / f"{receipt['index']:06d}.json.gz"
        dest = recovery / 'episodes' / episode.name
        if not dest.exists():
            assert sha(episode) == receipt['episode_sha256']
            copy_file(episode, dest)
            assert sha(dest) == receipt['episode_sha256']
            (recovery / 'receipts' / receipt_path.name).write_bytes(receipt_bytes)
        else:
            assert (recovery / 'receipts' / receipt_path.name).read_bytes() == receipt_bytes
        rows.append(receipt)
    snapshot_state = state(rows, m)
    snapshot_state['failures'] = len(list((recovery / 'failures').glob('*.json')))
    atomic_json(recovery / 'state.json', snapshot_state)
    heartbeat = json.loads((RUN / 'heartbeat.json').read_text())
    heartbeat.update(workers=m['worker_lifecycle']['normal_workers'], ben_workers=0,
                     completed=len(rows))
    atomic_json(recovery / 'heartbeat.json', heartbeat)
    if not (recovery / 'runtime').exists():
        shutil.copytree(RUNTIME, recovery / 'runtime', ignore=shutil.ignore_patterns('__pycache__', '.git'))
    for name in ('stream.json', 'prepare_stream.py', 'publish_stream.py',
                 'supervise_stream.py', 'instruction-watch.json', 'report_capture.py',
                 'publisher-maintenance.json', 'phase1_fleet.py', 'supervise_gen7.py',
                 'test_phase1_fleet.py', 'gen7-transition.json', 'gen6-final-publication.json',
                 'gen7-selfplay-transition.json', 'gen7-phase1-final-publication.json', 'guard-maintenance.json',
                 'gen7-selfplay-before-capture-final-publication.json', 'capture-diagnosis.json',
                 'gen71_gate.py', 'supervise_gen71.py', 'test_gen71_gate.py',
                 'gen71-transition.json', 'gen70-capture-final-publication.json'):
        if (BASE / name).exists():
            copy_file(BASE / name, recovery / 'operations' / name)
    if CONFIG.get('preparation_script'):
        copy_file(Path(CONFIG['preparation_script']), recovery / 'operations' / 'prepare_owned.py')
    for path in CONFIG.get('validation_logs', []):
        copy_file(Path(path), recovery / 'operations' / 'validation' / Path(path).name)
    export(recovery, OUT)
    data_path = OUT / 'arena/data.json'
    data = json.loads(data_path.read_text())
    # An idle BEN executor exists in the shared runtime, but this stream starts no BEN workers.
    data['configured_workers'] = m['worker_lifecycle']['normal_workers']
    data['collection']['workers'] = m['worker_lifecycle']['normal_workers']
    data['generation'] = m.get('effective_generation', m['generation'])
    if m.get('gen71_gate'):
        data['gen71_gate'] = m['gen71_gate']
        progress = RUN / 'gen71-gate-progress.json'
        if progress.exists():
            data['gen71_gate_progress'] = json.loads(progress.read_text())
    if m.get('phase1'):
        data['phase1'] = m['phase1']
        progress = RUN / 'phase1-global-progress.json'
        if progress.exists():
            data['phase1_progress'] = json.loads(progress.read_text())
    if (RUN / 'STOP').exists() or snapshot_state['complete'] or snapshot_state['failures']:
        data['collection']['running'] = False
        data['collection']['status'] = 'stopped' if (RUN / 'STOP').exists() else 'complete' if snapshot_state['complete'] else 'failed'
    atomic_json(data_path, data)
    git('add', '-A')
    # Scientific artifacts include binaries and models normally ignored by source checkouts.
    git('add', '-f', 'recovery')
    if git('status', '--porcelain'):
        git('commit', '-m', f"{m.get('title', 'Collection')}: {len(rows)} verified deals")
    git('push', '-u', 'origin', f"HEAD:refs/heads/{CONFIG['branch']}")
    commit = git('rev-parse', 'HEAD')
    actual = git('ls-remote', '--heads', 'origin', CONFIG['branch']).split()[0]
    assert actual == commit, 'Remote publication ref does not match the snapshot'
    atomic_json(RUN / 'publisher-status.json', dict(status='published', epoch=time.time(),
                completed=len(rows), commit=commit, branch=CONFIG['branch']))
    return snapshot_state['complete']


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    if not (OUT / '.git').exists():
        subprocess.run(['git', 'init', '--initial-branch', CONFIG['branch'], str(OUT)], check=True)
        git('remote', 'add', 'origin', 'https://github.com/maxschireson/Single-Dummy-Bridge.git')
    with (RUN / '.publisher.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        atomic_json(RUN / 'publisher-process.json', dict(pid=os.getpid(), epoch=time.time()))
        while not (RUN / 'PUBLISH_STOP').exists():
            try:
                complete = publish()
                if complete or args.once:
                    break
            except Exception as exc:
                atomic_json(RUN / 'publisher-status.json', dict(status='retrying',
                            epoch=time.time(), error=repr(exc)))
                if args.once:
                    raise
            time.sleep(60)
