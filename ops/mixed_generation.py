"""Initialize, resume, inspect, and supervise the mixed branching arena.

No work is launched at import time. All monitor agents may run status; only one
supervisor and one writer can hold their independent OS-owned locks.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
from copy import deepcopy
import fcntl
import json
import multiprocessing as mp
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.bidding_env import deal_key
from bridge_harness.corpus import load, save
from bridge_harness.improvement import read, writer_lock
from bridge_harness.loop_registry import sha, source_hash
from bridge_harness.mixed_arena import compact, mixture, run_board, summarize, validate_pair, verify_generation
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest


def freeze_spec(root, name, belief=None, policy=None, belief_kind='public'):
    dest = root/'artifacts'/name
    dest.mkdir(parents=True, exist_ok=True)
    spec = dict(id=name, belief_kind=belief_kind, samples=32, near_tie=.125, exploration=0., artifact_sha256={})
    for key, source in (('belief', belief), ('policy', policy)):
        if source:
            out = dest/(key+'.npz'); shutil.copy2(source, out)
            spec[key] = str(out.relative_to(root)); spec['artifact_sha256'][key] = sha(out)
    spec['identity'] = digest(spec)
    return spec


def initialize(root, corpus, belief, policy, old_belief, old_policy, exclusions, target=25000, generation=1):
    if (root/'manifest.json').exists(): raise ValueError('Use the existing frozen manifest')
    root.mkdir(parents=True, exist_ok=True)
    blocked = set()
    for p in exclusions:
        d = read(p)
        if isinstance(d, dict):
            blocked.update(k for k in d if len(k) == 64)
            for value in d.values():
                if isinstance(value, list): blocked.update(v for v in value if isinstance(v, str))
        else: blocked.update(v['family'] for v in d if isinstance(v, dict) and 'family' in v)
    boards = []; seen = set(); excluded = 0
    for board in load(corpus):
        family = deal_key(board.hands, True)
        legacy_overlap = any(digest(board.hands[j:]+board.hands[:j]) in blocked for j in range(4))
        if not board.contract or family in blocked or family in seen or legacy_overlap:
            excluded += 1; continue
        boards.append(board); seen.add(family)
        if len(boards) == target: break
    if len(boards) != target: raise ValueError(f'Only {len(boards)} eligible contracted deals')
    save(boards, root/'corpus.jsonl')
    bots = {
        'auction-policy-v2': freeze_spec(root, 'auction-policy-v2', belief, policy),
        'public-belief-v2': freeze_spec(root, 'public-belief-v2', belief, old_policy),
        'combined-v2': freeze_spec(root, 'combined-v2', old_belief, old_policy, 'auction'),
        'pimc-v1': freeze_spec(root, 'pimc-v1')}
    m = dict(schema='mixed-fork-generation-v1', generation=generation, target=target,
        candidate='auction-policy-v2', reference='public-belief-v2', bots=bots,
        roster=list(bots), mixture=mixture(list(bots)), seed=202611091902,
        corpus='corpus.jsonl', corpus_sha256=sha(root/'corpus.jsonl'), source_sha256=source_hash(),
        runtime_sha256={p:sha(ROOT/p) for p in ('ops/mixed_generation.py','ops/finish_mixed_generation.py')},
        input_corpus_sha256=sha(corpus), excluded_input_rows=excluded,
        exclusion_sources={str(p): sha(p) for p in exclusions},
        audit=dict(probability=.5, multiplier=3., max_depth=2, max_forks=64),
        demotion_looks=sorted({min(target, n) for n in (500, 1000, 2500, 5000, 10000, 25000, target)}),
        created_epoch=time.time(), next_generation_target=min(250000, 2*target),
        admission='Newest prediction-validated belief and trial policy start first; demote on scheduled negative paired IMP evidence.',
        pair_protocol='Two complete tables: candidate and prior version in the SAME focal seats against the SAME sampled historical partnership. Focal side randomized before play; identical auction and RNG streams.',
        policy_training='Audited one-move IMP contrasts only. Complete trajectories train beliefs. No future labels enter actors.',
        validation='Canonical deal-family split, 80% train / 20% validation; all descendants stay together.',
        boundary='At target train successor even when IMP evidence is inconclusive; keep frozen comparisons and historical versions.')
    m['identity'] = digest(m)
    atomic_json(root/'manifest.json', m)
    atomic_json(root/'state.json', summarize([], m))
    return m


def receipts(root, manifest, audit=False):
    rows = []
    episode_paths = sorted((root/'episodes').glob('*.json.gz'))
    boards = load(root/manifest['corpus']) if audit else None
    for p in episode_paths:
        receipt = root/'receipts'/(p.name.removesuffix('.json.gz')+'.json')
        if receipt.exists() and not audit:
            row = read(receipt)
            if row['manifest_identity'] != manifest['identity']: raise ValueError('Receipt identity mismatch')
        else:
            r = read(p)
            if audit: validate_pair(r, manifest, boards[r['index']], r['index'])
            if r['manifest_identity'] != manifest['identity']: raise ValueError('Episode identity mismatch')
            row = dict(compact(r), episode_sha256=sha(p), manifest_identity=manifest['identity'])
            if receipt.exists() and read(receipt) != row: raise ValueError('Episode or receipt changed')
            atomic_json(receipt, row)
        rows.append(row)
    if len({r['index'] for r in rows}) != len(rows) or len({r['family'] for r in rows}) != len(rows):
        raise ValueError('Duplicate committed deal')
    return rows


def collect(root, seconds, workers):
    with writer_lock(root):
        m = read(root/'manifest.json'); verify_generation(root, m)
        boards = load(root/m['corpus']); rows = receipts(root, m)
        done = {r['index'] for r in rows}
        until = time.monotonic()+seconds
        failures = list((root/'failures').glob('*.json'))
        if failures: raise RuntimeError(f'Inspect preserved failure before resuming: {failures[0]}')
        # SQLite WAL shares exact deterministic DDS answers across worker processes.
        os.environ['BRIDGE_DDS_CACHE'] = str(root/'dds-cache.sqlite')
        pending = {}; jobs = iter(i for i in range(len(boards)) if i not in done)
        atomic_json(root/'heartbeat.json', dict(epoch=time.time(), phase='collecting', completed=len(done), workers=workers))
        with ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context('spawn')) as pool:
            def submit():
                if time.monotonic() >= until or (root/'STOP').exists(): return
                index = next(jobs, None)
                if index is not None:
                    pending[pool.submit(run_board, str(root), m, boards[index].to_dict(), index)] = index
            for _ in range(workers): submit()
            while pending:
                completed, _ = wait(pending, timeout=15, return_when=FIRST_COMPLETED)
                atomic_json(root/'heartbeat.json', dict(epoch=time.time(), phase='collecting',
                    completed=len(rows), in_flight=sorted(pending.values()), workers=workers))
                for future in completed:
                    index = pending.pop(future)
                    try: r = future.result()
                    except BaseException:
                        atomic_json(root/'failures'/f'{index:06}.json', dict(index=index, epoch=time.time(), traceback=traceback.format_exc()))
                        raise
                    path = root/'episodes'/f'{index:06}.json.gz'
                    if path.exists(): raise ValueError('Refusing to overwrite completed board')
                    atomic_json(path, r, compressed=True)
                    row = dict(compact(r), episode_sha256=sha(path), manifest_identity=m['identity'])
                    atomic_json(root/'receipts'/f'{index:06}.json', row); rows.append(row)
                    state = summarize(rows, m); atomic_json(root/'state.json', state)
                    print(json.dumps({k: state[k] for k in ('completed','target','total_imps','audited_deviations','tables','best')}), flush=True)
                    submit()
        atomic_json(root/'state.json', summarize(rows, m))


def supervised_command(args, root, timeout):
    with (root/'worker.log').open('a') as log:
        child = subprocess.Popen(args, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = child.wait(timeout=timeout)
            if code: raise RuntimeError(f'Worker exit {code}; see {root}/worker.log')
        except BaseException:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
                try: child.wait(timeout=5)
                except subprocess.TimeoutExpired: os.killpg(child.pid, signal.SIGKILL); child.wait()
            raise


def supervise(root, seconds, workers):
    with (root/'.supervisor.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        while not (root/'STOP').exists():
            m = read(root/'manifest.json'); state = summarize(receipts(root, m), m)
            atomic_json(root/'state.json', state)
            if state['complete']:
                atomic_json(root/'training-request.json', dict(generation=m['generation'], root=str(root),
                    manifest_sha256=sha(root/'manifest.json'), reason='25k boundary reached; no IMP significance wait',
                    best=state['best'], next_target=m['next_generation_target'], status='ready'))
                if (root/'training-config.json').exists():
                    supervised_command([sys.executable, 'ops/finish_mixed_generation.py', '--run', str(root)], root, 172800)
                    if (root/'next-generation.json').exists():
                        next_root = Path(read(root/'next-generation.json')['run'])
                        return supervise(next_root, seconds, workers)
                return
            before = state['completed']
            supervised_command([sys.executable, 'ops/mixed_generation.py', 'collect', '--run', str(root),
                '--seconds', str(seconds), '--workers', str(workers)], root, seconds+900)
            after = read(root/'state.json')
            if after['completed'] <= before and not (root/'STOP').exists(): raise RuntimeError('Slice made no progress')
            atomic_json(root/'supervisor.json', dict(epoch=time.time(), completed=after['completed'], workers=workers,
                seconds=seconds, state='between-slices'))
            print(json.dumps(dict(completed=after['completed'], target=after['target'], phase='slice-committed')), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['init','collect','supervise','status'])
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--seconds', type=float, default=240); p.add_argument('--workers', type=int, default=4)
    p.add_argument('--target', type=int, default=25000); p.add_argument('--audit', action='store_true')
    for key in ('corpus','belief','policy','old-belief','old-policy'): p.add_argument('--'+key, type=Path)
    p.add_argument('--exclude', type=Path, action='append', default=[])
    a = p.parse_args(); root = a.run.resolve()
    if a.command == 'init':
        m = initialize(root, a.corpus, a.belief, a.policy, a.old_belief, a.old_policy, a.exclude, a.target)
        print(json.dumps(dict(generation=m['generation'], target=m['target'], mixture=m['mixture'])))
    elif a.command == 'collect': collect(root, a.seconds, a.workers)
    elif a.command == 'supervise': supervise(root, a.seconds, a.workers)
    else:
        m = read(root/'manifest.json'); verify_generation(root, m)
        print(json.dumps(summarize(receipts(root, m, a.audit), m), indent=2))


if __name__ == '__main__': main()
