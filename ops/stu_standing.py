#!/usr/bin/env python3
"""Opt-in Stu collection fallback and idle heartbeat; stdlib only, Linux operator tool."""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

ORIGIN = 1_000_000_000
STRIDE = 10_000_000


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    with tmp.open('w') as f:
        json.dump(value, f, indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@contextlib.contextmanager
def locked(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def recipe(path):
    r = json.loads(path.read_text())
    required = {'box', 'seed', 'workers', 'deals', 'options', 'name_prefix'}
    if ('pair' in r) == ('pairs' in r):
        raise ValueError('provide exactly one of pair or pairs')
    required.add('pair' if 'pair' in r else 'pairs')
    if set(r) != required:
        raise ValueError('recipe must contain exactly ' + ', '.join(sorted(required)))
    if type(r['box']) is not int or not 1 <= r['box'] <= 7:
        raise ValueError('box must be an integer 1..7')
    if r['seed'] != 9001 or type(r['seed']) is not int:
        raise ValueError('standing collection seed must be 9001')
    pairs = r.get('pairs', [r.get('pair')])
    if not isinstance(pairs, list) or not pairs or any(not isinstance(pair, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+~[A-Za-z0-9_.-]+', pair) for pair in pairs):
        raise ValueError('invalid pair')
    if not isinstance(r['name_prefix'], str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,39}', r['name_prefix']):
        raise ValueError('invalid name_prefix')
    for key, maximum in [('workers', 64), ('deals', 100_000)]:
        if type(r[key]) is not int or not 1 <= r[key] <= maximum:
            raise ValueError('invalid ' + key)
    options = r['options']
    if not isinstance(options, list) or any(not isinstance(x, str) for x in options):
        raise ValueError('options must be an argv list')
    i = 0
    while i < len(options):
        if options[i] in ('--episodes', '--one-room', '--common-only'):
            i += 1
        elif options[i] == '--recycle' and i + 1 < len(options) and options[i + 1].isdigit() and int(options[i + 1]) > 0:
            i += 2
        else:
            raise ValueError('unsupported collection option: ' + options[i])
    return r


def run(recipe_path, work, runner, max_jobs=None):
    """Reserve a fresh band before launch. Never retry interrupted or failed jobs."""
    work.mkdir(parents=True, exist_ok=True)
    with locked(work / 'standing.lock'):
        completed = 0
        while max_jobs is None or completed < max_jobs:
            if (work / 'FALLBACK_STOP').exists() or not recipe_path.exists():
                return 0
            r = recipe(recipe_path)
            first = ORIGIN + (r['box'] - 1) * STRIDE
            end = first + STRIDE
            state_path = work / 'standing-state.json'
            state = json.loads(state_path.read_text()) if state_path.exists() else {'box': r['box'], 'next': first, 'status': 'new'}
            if state['box'] != r['box'] or not first <= state['next'] <= end:
                raise ValueError('state does not belong to this box/band')
            if state['status'] not in ('new', 'complete'):
                raise RuntimeError('previous fallback is unfinished/failed; operator inspection required')
            start = state['next']
            if start + r['deals'] > end:
                raise RuntimeError('reserved box band exhausted')
            name = f"{r['name_prefix']}-fb{r['box']}-{start}"
            if (work / 'runs' / name).exists():
                raise RuntimeError('existing run identity: refusing to resume or overwrite')
            digest = hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest()
            pairs = r.get('pairs', [r.get('pair')])
            job = state.get('jobs_reserved', 0)
            pair = pairs[job % len(pairs)]
            state.update(jobs_reserved=job+1, pair=pair, next=start + r['deals'], status='reserved', name=name, first=start, deals=r['deals'], recipe_sha256=digest, recipe=r)
            atomic_json(state_path, state)
            cmd = ['bash', str(runner), name, pair, '9001', str(start), str(r['deals']), str(r['workers']), *r['options']]
            # Interrupted/reserved state is deliberately sticky across restarts.
            result = subprocess.run(cmd, check=False)
            state.update(status='complete' if result.returncode == 0 else 'failed', returncode=result.returncode)
            atomic_json(state_path, state)
            if result.returncode:
                return result.returncode if result.returncode > 0 else 1
            completed += 1
    return 0


def busy_token(token):
    path = Path(os.fsdecode(token))
    return (path.name in ('x8_match.py', 'train_rollout_net.py')
            or tuple(path.parts[-2:]) == ('bench', 'seat_variants.py')
            or 'stu_rollout_experiments' in path.parts and path.suffix == '.py')


def match_count(proc=Path('/proc')):
    count, unknown = 0, False
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            argv = (entry / 'cmdline').read_bytes().split(b'\0')
            if any(busy_token(x) for x in argv if x):
                count += 1
        except FileNotFoundError:
            pass  # process exited during snapshot
        except PermissionError:
            unknown = True
    return count if count or not unknown else None


def heartbeat_value(previous, active, now, boot):
    since = previous.get('idle_since_monotonic') if previous.get('boot_id') == boot else None
    if active is None or active > 0:
        since = None
    elif since is None or since > now:
        since = now
    idle = max(0, now - since) if since is not None else 0
    return dict(boot_id=boot, observed_at=time.time(), match_processes=active,
                idle_since_monotonic=since, idle_seconds=int(idle),
                idle_over_15m=active == 0 and idle > 900,
                observation='unknown' if active is None else 'observed')


def busy_count(work):
    if (work / 'BUSY').exists():
        return 1, 'operator BUSY marker'
    count = match_count()
    if count:
        return count, 'allowlisted process'
    try:
        result = subprocess.run(['systemctl', 'show', 'perf-ab.service', '--property=ActiveState', '--value'],
                                capture_output=True, text=True, timeout=5, check=False)
        state = result.stdout.strip()
        if result.returncode == 0 and state in ('active', 'activating', 'reloading', 'deactivating'):
            return 1, 'perf-ab.service'
        if result.returncode != 0 or state not in ('inactive', 'failed'):
            return None, 'unit observation unavailable'
    except (OSError, subprocess.TimeoutExpired):
        return None, 'unit observation unavailable'
    return count, 'process and unit snapshot'


def heartbeat(work):
    with locked(work / 'standing-heartbeat.lock'):
        path = work / 'pub' / 'collection-heartbeat.json'
        old = json.loads(path.read_text()) if path.exists() else {}
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        count, reason = busy_count(work)
        value = heartbeat_value(old, count, time.monotonic(), boot)
        value['busy_reason'] = reason
        value['busy_activities'] = value.pop('match_processes')
        atomic_json(path, value)
        return 2 if value['idle_over_15m'] else 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    run_parser = sub.add_parser('run')
    run_parser.add_argument('--recipe', type=Path, required=True)
    run_parser.add_argument('--runner', type=Path, required=True)
    run_parser.add_argument('--work', type=Path, required=True)
    hb = sub.add_parser('heartbeat')
    hb.add_argument('--work', type=Path, required=True)
    a = p.parse_args()
    try:
        return heartbeat(a.work) if a.command == 'heartbeat' else run(a.recipe, a.work, a.runner)
    except (OSError, ValueError, RuntimeError) as exc:
        p.exit(1, f'{exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
