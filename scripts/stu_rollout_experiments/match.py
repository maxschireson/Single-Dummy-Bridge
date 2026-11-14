#!/usr/bin/env python3
"""Fresh-only research runner: immutable identity, one attempt, inclusive costs.

Deliberately does not invoke the inherited fail-open resume/retry driver. Existing
output directories with any contents are refused before changing a byte. Restart
requires a new output identity; interrupted/failed attempts remain preserved.
"""
import argparse
import copy
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import time

RUNTIME = Path(os.environ['STU_RUNTIME']).resolve()
sys.path[:0] = [str(RUNTIME), str(RUNTIME / 'scripts')]
import x8_match
from engine import ExperimentalPlayer
from accounting import child_cpu
import engine
from bridge_harness.round5_ben import Round5BenPlayer

gm = x8_match.gen8_match

original = x8_match.player
class TimedBen(Round5BenPlayer):
    """Dedicated external BEN server: action wall includes HTTP/server work.

Server CPU is not a child of this worker and is deliberately not counted as
worker/native-SURE CPU. Compare candidate action time separately from BEN time.
"""
    def choose(self, o, rng):
        wall, cpu = time.perf_counter(), time.process_time()
        result = super().choose(o, rng)
        result.details['experiment_work'] = dict(wall_seconds=time.perf_counter()-wall,
            worker_cpu_seconds=time.process_time()-cpu, external_server_cpu_measured=False)
        return result


def player(spec, root, reference=None):
    if spec.get('engine') == 'ben':
        return TimedBen(spec['url'], timeout=600, samples=spec['samples'])
    if spec.get('rollout_experiment'):
        return ExperimentalPlayer(spec, root, reference)
    return original(spec, root, reference)

x8_match.player = player


def start_worker(source, manifest, endpoints=None):
    local = copy.deepcopy(manifest)
    if endpoints is not None:
        endpoint = endpoints.get(timeout=30)
        for spec in local['bots'].values():
            if spec.get('engine') == 'ben':
                spec['url'] = endpoint
    gm.start(source, local)

original_summary = x8_match.summarise_actions
def summarise_actions(record, roles):
    out = original_summary(record, roles)
    for role in roles:
        out[role]['experiment_work'] = {}
        out[role]['recursive'] = {}
        out[role]['precisions'] = []
    for table in record.values():
        for t in table['tables'][:1]:
            for action in t['actions']:
                role = action.get('role') or action.get('player')
                if role not in out:
                    continue
                for category in ('experiment_work', 'recursive'):
                    for key, value in action.get(category, {}).items():
                        if isinstance(value, (int, float)):
                            dest = out[role][category]
                            dest[key] = dest.get(key, 0) + value
                work = action.get('experiment_work', {})
                precision = [work.get('precision'), work.get('rollout_precision')]
                if precision[0] is not None and precision not in out[role]['precisions']:
                    out[role]['precisions'].append(precision)
    return out

x8_match.summarise_actions = summarise_actions
gm.summarise_actions = summarise_actions


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare_output(out, manifest):
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError('Refusing nonempty output directory; use a fresh run identity')
    out.mkdir(parents=True, exist_ok=True)
    # Exclusive create also protects against a simultaneous launcher.
    with (out / 'manifest.json').open('x') as f:
        json.dump(manifest, f, indent=2)
    (out / 'attempts').mkdir()
    (out / 'episodes').mkdir()


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def attempt(index, seed, out, episodes):
    path = Path(out) / 'attempts' / f'{index:06d}.json'
    wall, cpu, native = time.perf_counter(), time.process_time(), child_cpu()
    status = dict(index=index, seed=seed, attempt=1, status='running', pid=os.getpid(),
                  started=time.strftime('%FT%TZ', time.gmtime()))
    atomic_json(path, status)
    try:
        row = gm.play(index, seed, str(Path(out) / 'episodes') if episodes else None)
    except BaseException as error:
        status.update(status='failed', error=f'{type(error).__name__}: {error}')
        raise
    else:
        status['status'] = 'complete'
    finally:
        status.update(wall_seconds=time.perf_counter()-wall,
                      worker_cpu_seconds=time.process_time()-cpu,
                      solver_cpu_seconds=child_cpu()-native)
        status['inclusive_cpu_seconds'] = status['worker_cpu_seconds'] + status['solver_cpu_seconds']
        atomic_json(path, status)
    row['attempt_work'] = {k: v for k, v in status.items() if k.endswith('_seconds')}
    row['ben_endpoints'] = [s['url'] for s in gm.STATE.get('m', {}).get('bots', {}).values() if s.get('engine') == 'ben']
    return row


def summarize(rows, pair, out):
    result = gm.summary(rows, *pair.split('~'))
    ledger = [json.loads(p.read_text()) for p in (Path(out) / 'attempts').glob('*.json')]
    result.update(failures=sum(a['status'] == 'failed' for a in ledger),
                  unfinished=sum(a['status'] == 'running' for a in ledger), attempts=len(ledger),
                  interpretation='development only; not a strength or equal-time decision',
                  cpu_per_board_scope='legacy Python worker CPU; excludes external solver')
    result['attempt_cpu_scope'] = 'worker plus reaped child solvers; separately hosted BEN server CPU excluded'
    result['attempt_work'] = {k: sum(a.get(k, 0.) for a in ledger) for k in
        ('wall_seconds', 'worker_cpu_seconds', 'solver_cpu_seconds', 'inclusive_cpu_seconds')}
    actors = result['actors'] = {}
    for row in rows:
        for role in ('candidate', 'opponent'):
            name = row[role]
            actor = actors.setdefault(name, dict(work={}, recursive={}, precisions=[]))
            search = row.get('search', {}).get(role, {})
            for category, target in (('experiment_work', 'work'), ('recursive', 'recursive')):
                for key, value in search.get(category, {}).items():
                    actor[target][key] = actor[target].get(key, 0.) + value
            for precision in search.get('precisions', []):
                if precision not in actor['precisions']:
                    actor['precisions'].append(precision)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--bots', type=Path, required=True)
    ap.add_argument('--pair', required=True)
    ap.add_argument('--deals', type=int, required=True)
    ap.add_argument('--first', type=int, default=0)
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--episodes', action='store_true')
    ap.add_argument('--common-only', action='store_true', required=True)
    ap.add_argument('--recycle', type=int, default=4)
    ap.add_argument('--ben-urls', help='Comma-separated dedicated BEN endpoints, exactly one per worker')
    ap.add_argument('--ben-provenance', type=Path, help='Pinned BEN revision/config/model manifest')
    args = ap.parse_args()
    if min(args.deals, args.workers, args.recycle) <= 0 or args.first < 0:
        ap.error('Positive deals/workers/recycle and nonnegative first are required')
    source, out = args.source.resolve(), args.out.resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError('Refusing nonempty output directory; use a fresh run identity')
    m = gm.build_manifest(source, args.bots, args.pair, args.seed)
    m['common_only'] = True
    m.pop('identity', None)
    m['identity'] = gm.digest(m)
    has_ben = any(m['bots'][key].get('engine') == 'ben' for key in m['roster'])
    urls = args.ben_urls.split(',') if args.ben_urls else []
    if has_ben and (len(urls) != args.workers or len(set(urls)) != len(urls) or not args.ben_provenance):
        raise ValueError('BEN requires one unique dedicated endpoint per worker and pinned provenance')
    if not has_ben and (urls or args.ben_provenance):
        raise ValueError('BEN arguments require a BEN actor')
    assets = {}
    for spec in m['bots'].values():
        for key in ('gen7_policy', 'rollout_policy', 'bidding', 'scorer', 'lead_belief', 'belief', 'lead_state_bidder'):
            if spec.get(key):
                path = (source / spec[key]).resolve()
                assets[str(path)] = sha256(path)
    for path in [RUNTIME / 'bridge_harness/libbridge_dds.so', Path(os.environ['SURE_BIN']),
                 *sorted((RUNTIME / 'bridge_harness').glob('*.py')),
                 RUNTIME / 'scripts/gen8_match.py', RUNTIME / 'scripts/x8_match.py']:
        assets[str(path)] = sha256(path)
    expected = sha256(engine.__file__)
    for actor in m['roster']:
        if m['bots'][actor].get('engine') == 'ben':
            assets[str(args.ben_provenance.resolve())] = sha256(args.ben_provenance)
            continue
        e = m['bots'][actor].get('rollout_experiment', {})
        if e.get('implementation_sha256') != expected or not e.get('isolate_claims'):
            raise ValueError('Every actor requires pinned experiment implementation and isolated solvers')
    manifest = dict(m, source=str(source), first=args.first, deals=args.deals, workers=args.workers,
        seed=args.seed, episodes=args.episodes, recycle=args.recycle, assets=assets,
        source_commit=subprocess.check_output(['git', '-C', str(RUNTIME), 'rev-parse', 'HEAD'], text=True).strip(),
        implementation={p.name: sha256(p) for p in Path(__file__).parent.glob('*.py')},
        environment={key: os.environ.get(key) for key in
            ('BRIDGE_NET_BF16', 'OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'BRIDGE_DDS_CACHE')},
        protocol_version=2, retry_policy='none; preserve first failure and stop', run_identity=str(out))
    if has_ben:
        manifest['ben'] = dict(endpoints=urls, provenance=json.loads(args.ben_provenance.read_text()),
                              cpu_scope='external server CPU excluded; dedicated-server action wall recorded')
    prepare_output(out, manifest)
    rows, failure = [], None
    todo = list(range(args.first, args.first+args.deals))
    with (out / 'results.jsonl').open('x') as results:
        size = args.recycle * args.workers
        for lo in range(0, len(todo), size):
            endpoints = multiprocessing.Queue() if has_ben else None
            if endpoints is not None:
                for url in urls:
                    endpoints.put(url)
            with ProcessPoolExecutor(args.workers, initializer=start_worker, initargs=(str(source), m, endpoints)) as pool:
                jobs = {pool.submit(attempt, index, args.seed, str(out), args.episodes): index for index in todo[lo:lo+size]}
                for job in as_completed(jobs):
                    if job.cancelled():
                        continue
                    try:
                        row = job.result()
                    except Exception as error:
                        failure = failure or f'board {jobs[job]}: {type(error).__name__}: {error}'
                        for other in jobs:
                            other.cancel()
                    else:
                        if row['index'] != jobs[job] or row['family'] in {r['family'] for r in rows}:
                            raise RuntimeError('Unexpected index or duplicate deal family')
                        rows.append(row)
                        results.write(json.dumps(row) + '\n')
                        results.flush()
                    report = summarize(rows, args.pair, out)
                    report['driver_failure'] = failure
                    atomic_json(out / 'summary.json', report)
                    print(json.dumps(dict(boards=len(rows), common=report.get('common'), failure=failure)), flush=True)
            if failure:
                raise RuntimeError(failure)
            if endpoints is not None:
                endpoints.close()
                endpoints.join_thread()
    if len(rows) != args.deals:
        raise RuntimeError('Incomplete run')


if __name__ == '__main__':
    main()
