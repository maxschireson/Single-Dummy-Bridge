"""Operational collection launcher; does not alter frozen campaign code/settings.

A slice stops submitting work after its soft deadline, drains all submitted
boards, and retains the normal atomic records. A supervisor starts the next
slice immediately. Neither can survive destruction of its enclosing runtime.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import json
import os
from pathlib import Path
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


class SliceComplete(Exception):
    pass


def bounded_slice(fn, jobs, workers, deadline, clock=time.monotonic):
    jobs = iter(jobs)
    exhausted = False
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = set()

        def submit():
            nonlocal exhausted
            if exhausted or clock() >= deadline:
                return
            try:
                job = next(jobs)
            except StopIteration:
                exhausted = True
                return
            pending.add(pool.submit(fn, job))

        for _ in range(workers):
            submit()
        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                yield future.result()  # Failure is fatal, never silently skipped.
                submit()
    if not exhausted:
        # Permit a completed shard to finalize even if its last board crossed
        # the deadline. Otherwise the enclosing collect must stop before fitting.
        try:
            next(jobs)
        except StopIteration:
            return
        raise SliceComplete()


def snapshot(root):
    generation = json.loads((root / 'state.json').read_text())['generation']
    files = list((root / f'g{generation}' / 'selfplay').glob('*/episodes/*.json.gz'))
    mem = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        name, value = line.split(':', 1)
        if name in ('MemTotal', 'MemAvailable', 'SwapTotal'):
            mem[name + '_kib'] = int(value.split()[0])
    rss_kib = 0
    processes = 0
    for status in Path('/proc').glob('[0-9]*/status'):
        try:
            for line in status.read_text().splitlines():
                if line.startswith('VmRSS:'):
                    rss_kib += int(line.split()[1])
                    processes += 1
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
    return dict(records=len(files), newest_epoch=max((p.stat().st_mtime for p in files), default=None),
                memory=mem, load=os.getloadavg(), visible_processes=processes,
                visible_process_rss_sum_kib=rss_kib)


def event(root, name, **fields):
    record = dict(event=name, epoch=time.time(), pid=os.getpid(), **fields)
    line = json.dumps(record)
    with (root / 'slice-events.jsonl').open('a') as f:
        f.write(line + '\n')
        f.flush()
    print(line, flush=True)


def run_slice(args):
    from bridge_harness import improvement as imp
    started = time.monotonic()
    deadline = started + args.seconds
    # Only change scheduling. Board identities, settings, weights, seeds,
    # validation, auctions, targets, and source hashes remain unchanged.
    imp.bounded_map = lambda fn, jobs, workers: bounded_slice(
        fn, jobs, min(workers, args.workers), deadline)
    with imp.writer_lock(args.root):
        campaign = imp.Campaign(args.root)
        try:
            campaign.preflight()
            if campaign.state['status'] not in ('prepared', 'collecting'):
                event(args.root, 'phase_requires_campaign_runner', status=campaign.state['status'])
                return 20
            generation = campaign.state['generation']
            target = campaign.state.get('training_deals') or campaign.config['settings']['training_stages'][0]
            campaign.checkpoint(status='collecting', training_deals=target)
            event(args.root, 'slice_start', seconds=args.seconds, workers=args.workers, **snapshot(args.root))
            try:
                with campaign.timed('collection'):
                    dataset = campaign.collect(generation, target, campaign.state['champion'])
            except SliceComplete:
                event(args.root, 'slice_complete', elapsed=time.monotonic()-started, **snapshot(args.root))
                return 0
            event(args.root, 'collection_complete', dataset=str(dataset), elapsed=time.monotonic()-started,
                  **snapshot(args.root))
            return 20
        finally:
            campaign.close()


def supervise(args):
    import fcntl
    with (args.root / '.slice-supervisor.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        event(args.root, 'supervisor_start', seconds=args.seconds, workers=args.workers, **snapshot(args.root))
        iteration = 0
        while True:
            # An already-running campaign owns its own namespace. Respect its
            # OS lock; an empty process listing is not evidence of termination.
            with (args.root / '.writer.lock').open('a+') as writer:
                try:
                    fcntl.flock(writer, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(writer, fcntl.LOCK_UN)
                except BlockingIOError:
                    event(args.root, 'waiting_existing_writer', **snapshot(args.root))
                    time.sleep(20)
                    continue
            iteration += 1
            argv = [sys.executable, str(Path(__file__).resolve()), 'slice', '--root', str(args.root),
                    '--seconds', str(args.seconds), '--workers', str(args.workers)]
            with (args.root / 'worker.log').open('a') as log:
                child = subprocess.Popen(argv, cwd=REPO, stdout=log, stderr=subprocess.STDOUT)
                event(args.root, 'child_start', child_pid=child.pid, iteration=iteration)
                while child.poll() is None:
                    try:
                        child.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        event(args.root, 'heartbeat', child_pid=child.pid, iteration=iteration, **snapshot(args.root))
                event(args.root, 'child_exit', child_pid=child.pid, returncode=child.returncode,
                      iteration=iteration, **snapshot(args.root))
            if child.returncode == 20:
                event(args.root, 'ready_for_campaign_runner')
                return 0
            if child.returncode != 0:
                # Infrastructure or invalid records require review, not a hot retry loop.
                return child.returncode if child.returncode > 0 else 1


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=('slice', 'supervise'))
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--seconds', type=float, default=240)
    p.add_argument('--workers', type=int, default=4)
    args = p.parse_args()
    args.root = args.root.resolve()
    if args.seconds <= 0 or args.workers < 1:
        p.error('seconds and workers must be positive')
    return run_slice(args) if args.mode == 'slice' else supervise(args)


if __name__ == '__main__':
    sys.exit(main())
