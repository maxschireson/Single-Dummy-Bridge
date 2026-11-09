"""Resume frozen arena games while honoring an explicit matchup cancellation.

The original collector, model/runtime hashes, manifest, and per-index matchups
remain unchanged. A separate immutable plan cancels only unplayed 4-vs-4 slots.
"""
import argparse
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
import fcntl
import gzip
import json
import multiprocessing as mp
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import run_supplemental_arena as frozen
from bridge_harness.fork_audit import stream
from bridge_harness.v4_arena import schedule


def scheduled_pair(manifest, index):
    pairs = manifest.get('pair_schedule')
    if pairs:
        block = list(pairs)
        stream(manifest['seed'], 'pair-block', index // len(block)).shuffle(block)
        pair = block[index % len(block)]
        if isinstance(pair, str):
            pair = pair.split('~') if '~' in pair else list(pair)
        if len(pair) != 2:
            raise ValueError('Invalid frozen pair')
        return tuple(pair)
    return manifest['roster'][0], schedule(manifest, index)


def cancellation_plan(manifest, done):
    excluded = {i for i in range(manifest['target'])
                if scheduled_pair(manifest, i) == ('4', '4')}
    skipped = sorted(excluded - done)
    plan = dict(schema='arena-collection-cancellation-v1',
                manifest_identity=manifest['identity'],
                reason="Max requested no new Gen4-versus-Gen4 games on 2026-11-09.",
                excluded_pairs=[['4', '4']], frozen_target=manifest['target'],
                skipped_indices=skipped, retained_self_indices=sorted(excluded & done),
                target=manifest['target'] - len(skipped))
    plan['identity'] = frozen.digest(plan)
    return plan


def verify_plan(plan, manifest, done):
    if frozen.digest({k: v for k, v in plan.items() if k != 'identity'}) != plan['identity']:
        raise ValueError('Collection plan changed')
    if plan != cancellation_plan(manifest, done):
        raise ValueError('Collection plan differs from frozen schedule/completed episodes')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--seconds', type=float, default=86400)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    root = args.run.resolve()
    manifest = json.loads((root / 'manifest.json').read_text())
    lock = (root / 'writer.lock').open('a+')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if frozen.digest({k: v for k, v in manifest.items() if k != 'identity'}) != manifest['identity']:
        raise ValueError('Manifest changed')
    if frozen.sha(root / manifest['corpus']) != manifest['corpus_sha256']:
        raise ValueError('Corpus changed')
    repo = Path(__file__).resolve().parents[1]
    for name, checksum in manifest.get('runtime_sha256', {}).items():
        if frozen.sha(repo / name) != checksum:
            raise ValueError('Runtime changed: ' + name)
    for spec in manifest['bots'].values():
        for name, checksum in spec['artifact_sha256'].items():
            if frozen.sha(root / spec[name]) != checksum:
                raise ValueError('Model changed')
    done = set()
    for path in (root / 'episodes').glob('*.json.gz'):
        with gzip.open(path, 'rt') as handle:
            record = json.load(handle)
        index = int(path.name.split('.')[0])
        if (record['manifest_identity'] != manifest['identity'] or record['index'] != index
                or not 0 <= index < manifest['target']):
            raise ValueError('Wrong episode')
        done.add(index)
    plan_path = root / 'collection-plan.json'
    template = repo / 'configs' / (root.name + '-collection-plan.json')
    source_plan = plan_path if plan_path.exists() else template
    plan = json.loads(source_plan.read_text()) if source_plan.exists() else cancellation_plan(manifest, done)
    verify_plan(plan, manifest, done)
    skipped = set(plan['skipped_indices'])
    if args.dry_run:
        print(json.dumps(dict(completed=len(done), target=plan['target'],
                              skipped_unplayed_self=len(skipped), retained_self=len(plan['retained_self_indices']),
                              remaining=plan['target'] - len(done), plan_identity=plan['identity'])))
        return
    if (root / 'STOP').exists():
        raise ValueError('STOP present; refusing to launch workers')
    if not plan_path.exists():
        frozen.atomic_json(plan_path, plan)
    boards = [json.loads(line) for line in (root / manifest['corpus']).read_text().splitlines()]
    jobs = iter(i for i in range(manifest['target']) if i not in done and i not in skipped)
    started = time.time()
    initial = len(done)
    pending = {}
    failures = 0
    stopping = False

    def status():
        frozen.atomic_json(root / 'status.json', dict(
            manifest_identity=manifest['identity'], completed=len(done), target=plan['target'],
            frozen_target=manifest['target'], skipped_unplayed_self=len(skipped),
            collection_plan_identity=plan['identity'], collection_complete=len(done) == plan['target'],
            workers=args.workers, in_flight=list(pending.values()), started_epoch=started,
            updated_epoch=time.time(), completed_this_session=len(done) - initial,
            session_per_hour=(len(done) - initial) * 3600 / max(time.time() - started, 1),
            failures=failures, stopping=stopping))

    status()
    with ProcessPoolExecutor(max_workers=args.workers, mp_context=mp.get_context('spawn'),
                             initializer=frozen.initialize, initargs=(str(root),)) as pool:
        def submit():
            if stopping or (root / 'STOP').exists():
                return
            index = next(jobs, None)
            if index is not None:
                if scheduled_pair(manifest, index) == ('4', '4'):
                    raise ValueError('Cancelled matchup reached worker queue')
                pending[pool.submit(frozen.play, (index, boards[index]))] = index
        for _ in range(args.workers):
            submit()
        while pending:
            finished, _ = wait(pending, timeout=5, return_when=FIRST_COMPLETED)
            for future in finished:
                index = pending.pop(future)
                try:
                    row = future.result()
                    done.add(index)
                    with (root / 'progress.jsonl').open('a') as handle:
                        handle.write(json.dumps(row) + '\n')
                    print(json.dumps(dict(completed=len(done), **row)), flush=True)
                except Exception as error:
                    failures += 1
                    with (root / 'errors.jsonl').open('a') as handle:
                        handle.write(json.dumps(dict(index=index, error=repr(error), epoch=time.time())) + '\n')
                    status()
                    raise
                stopping = time.time() - started >= args.seconds or (root / 'STOP').exists()
                submit()
            status()
    status()


if __name__ == '__main__':
    main()
