#!/usr/bin/env python3
"""Publish aggregate arena snapshots to Pages using Git; never publish episodes."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def git(database, *args, data=None, env=None):
    result = subprocess.run(['git', '--git-dir', str(database), *args], input=data,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env=env, timeout=90)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace').strip())
    return result.stdout.decode().strip()


def publish(source, state, remote, branch='gh-pages', destination='arena', data_only=False, interval=0, replay_run=None):
    if not destination or any(p in ('', '.', '..') for p in destination.split('/')):
        raise ValueError('Destination must be a safe, nonempty relative directory')
    if destination.startswith('/') or '\\' in destination:
        raise ValueError('Unsafe Pages destination')
    # Export an explicit allowlist only. No filesystem traversal or source checkout.
    html = (source/'index.html').read_bytes()
    raw = (source/'data.json').read_bytes()
    payload = json.loads(raw)
    if payload.get('labels') not in (dict(A='Gen 3.5', B='Gen 3', C='Gen 2'), {k:'Gen '+k for k in '4321'}):
        raise ValueError('Expected dashboard generation labels are missing')
    if not payload.get('manifest_identity'):
        raise ValueError('Missing source manifest identity')
    # Both files are atomically generated, but a refresh can occur between reads.
    # Refuse mismatched snapshots rather than publish an inconsistent pair.
    marker = f'"generated_epoch": {payload["generated_epoch"]}'.encode()
    if marker not in html:
        raise ValueError('Dashboard refreshed during read; retry next publication')
    if replay_run is not None:
        from ops.export_replays import export
        export(replay_run, source/'replays', title=payload['campaign'], cutoff=payload['generated_epoch'])
    state.mkdir(parents=True, exist_ok=True)
    database = state/'git'
    if not database.exists():
        subprocess.run(['git', 'init', '--bare', str(database)], check=True, capture_output=True)
    env = dict(os.environ, GIT_INDEX_FILE=str(state/'index'),
               GIT_AUTHOR_NAME='Bridge arena feed', GIT_COMMITTER_NAME='Bridge arena feed',
               GIT_AUTHOR_EMAIL='arena-feed@users.noreply.github.com',
               GIT_COMMITTER_EMAIL='arena-feed@users.noreply.github.com')
    ref = f'refs/heads/{branch}'
    git(database, 'check-ref-format', ref)
    found = git(database, 'ls-remote', remote, ref)
    parent = None
    if found:
        git(database, 'fetch', '--no-tags', remote, ref)
        parent = git(database, 'rev-parse', 'FETCH_HEAD')
        git(database, 'read-tree', parent, env=env)
    else:
        git(database, 'read-tree', '--empty', env=env)
    if data_only:
        published = time.time()
        payload['feed'] = dict(published_epoch=published, interval_seconds=interval,
                               next_update_epoch=published+interval if interval else None)
        raw = json.dumps(payload, allow_nan=False).encode()
    files = [('data.json', raw)] if data_only else [('index.html', html), ('data.json', raw)]
    replay_dir = source/'replays'
    if replay_dir.exists():
        extensions = {'.json'} if data_only else {'.json','.html','.js','.css'}
        for path in sorted(replay_dir.rglob('*')):
            if path.is_file() and path.suffix in extensions:
                if not path.resolve().is_relative_to(replay_dir.resolve()):
                    raise ValueError('Replay asset escapes export directory')
                files.append(('replays/'+str(path.relative_to(replay_dir)), path.read_bytes()))
    for name, content in files:
        blob = git(database, 'hash-object', '-w', '--stdin', data=content)
        git(database, 'update-index', '--add', '--cacheinfo',
            f'100644,{blob},{destination}/{name}', env=env)
    tree = git(database, 'write-tree', env=env)
    if parent and tree == git(database, 'rev-parse', parent+'^{tree}'):
        return dict(status='unchanged', commit=parent, completed=payload['completed'])
    args = ['commit-tree', tree]
    if parent:
        args += ['-p', parent]
    commit = git(database, *args, data=f'Update arena dashboard: {payload["completed"]} paired boards\n'.encode(), env=env)
    # Normal fast-forward push only. A concurrent publisher cannot be overwritten.
    git(database, 'push', remote, f'{commit}:{ref}')
    result = dict(status='published', commit=commit, completed=payload['completed'],
                  epoch=time.time(), source_epoch=payload['generated_epoch'],
                  branch=branch, destination=destination, manifest_identity=payload['manifest_identity'])
    result.update(data_only=data_only, next_update_epoch=payload.get('feed', {}).get('next_update_epoch'))
    temp = state/'last-publish.json.tmp'
    temp.write_text(json.dumps(result, indent=2)+'\n')
    temp.replace(state/'last-publish.json')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--state', type=Path, required=True)
    p.add_argument('--remote', required=True)
    p.add_argument('--branch', default='gh-pages')
    p.add_argument('--destination', default='arena')
    p.add_argument('--interval', type=float, default=0)
    p.add_argument('--data-only', action='store_true', help='Publish JSON to a separate non-Pages branch')
    p.add_argument('--replay-run', type=Path, help='Export committed root replays in the same feed commit')
    a = p.parse_args()
    if a.data_only and a.branch == 'gh-pages':
        p.error('Data-only updates require a separate non-Pages branch')
    minimum = 60 if a.data_only else 600
    if a.interval < 0 or (a.interval and a.interval < minimum):
        p.error(f'Use at least {minimum} seconds between updates in this mode')
    a.state.mkdir(parents=True, exist_ok=True)
    with (a.state/'.publisher.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        while not (a.state/'STOP').exists():
            started = time.monotonic()
            try:
                result = publish(a.source.resolve(), a.state.resolve(), a.remote, a.branch,
                                 a.destination, a.data_only, a.interval, a.replay_run)
                print(json.dumps(result), flush=True)
            except Exception as exc:
                error = dict(status='publish-failed', epoch=time.time(), error=str(exc))
                (a.state/'last-error.json').write_text(json.dumps(error, indent=2)+'\n')
                print(json.dumps(error), flush=True)
                if not a.interval:
                    raise
            if not a.interval:
                break
            deadline = started+a.interval
            while time.monotonic() < deadline and not (a.state/'STOP').exists():
                time.sleep(min(2, max(0, deadline-time.monotonic())))


if __name__ == '__main__':
    main()
