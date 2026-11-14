#!/usr/bin/env python3
"""Fetch a range of a feed branch's episodes from GitHub, without the rest of the branch.

  python scripts/plan_fetch.py --branch arena-gen6-fast-selfplay-20261111-19bbdce5-feed --first 5214 --last 6774 --out DIR [--work DIR]

An episode is a path */episodes/<index>.json.gz at the branch's tip; --first and --last bound the index
(inclusive). The tip is fetched without file contents and the wanted files are then fetched by id, so a
1,500-episode range of a 7,000-episode feed is about 270 MB and under a minute. Writes DIR/<index>.json.gz
and DIR/MANIFEST.json (branch, tip, range, count).
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import time

REPO = 'https://github.com/maxschireson/Single-Dummy-Bridge'
EPISODE = re.compile(r'(^|/)episodes/(\d+)\.json\.gz$')


def git(git_dir, *args, data=None, check=True):
    r = subprocess.run(['git', '--git-dir', str(git_dir), *args], input=data, capture_output=True)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args[:3])} failed: {r.stderr.decode(errors='replace')[-400:]}")
    return r


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--branch', required=True)
    p.add_argument('--first', type=int, default=0)
    p.add_argument('--last', type=int, default=10 ** 9)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--work', type=Path)
    p.add_argument('--chunk', type=int, default=200)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    store = (a.work or a.out) / 'fetch.git'
    if not (store / 'HEAD').exists():
        subprocess.run(['git', 'init', '--bare', '-q', str(store)], check=True)
        git(store, 'remote', 'add', 'origin', REPO)
        git(store, 'config', 'remote.origin.promisor', 'true')
        git(store, 'config', 'remote.origin.partialclonefilter', 'blob:none')
        git(store, 'config', 'gc.auto', '0')
    git(store, 'fetch', '-q', '--no-tags', '--depth=1', '--filter=blob:none', 'origin', f'+refs/heads/{a.branch}:refs/feeds/tip')
    tip = git(store, 'rev-parse', 'refs/feeds/tip').stdout.decode().strip()
    want = []
    for line in git(store, 'ls-tree', '-r', tip).stdout.decode().splitlines():
        meta, path = line.split('\t', 1)
        m = EPISODE.search(path)
        if m and a.first <= int(m[2]) <= a.last and not (a.out / f'{int(m[2]):06d}.json.gz').exists():
            want.append((meta.split()[2], int(m[2])))
    print(f'{a.branch} at {tip[:10]}: {len(want)} episodes to fetch', flush=True)
    for i in range(0, len(want), a.chunk):
        part = want[i:i + a.chunk]
        data = ('\n'.join(oid for oid, _ in part) + '\n').encode()
        for attempt in range(5):
            r = git(store, '-c', 'fetch.negotiationAlgorithm=noop', 'fetch', '-q', '--no-tags', '--no-write-fetch-head', '--recurse-submodules=no',
                    '--filter=blob:none', 'origin', '--stdin', data=data, check=False)
            if r.returncode == 0:
                break
            time.sleep(5 * (attempt + 1))
        else:
            raise SystemExit('fetch failed: ' + r.stderr.decode(errors='replace')[-300:])
        cat = subprocess.Popen(['git', '--git-dir', str(store), 'cat-file', '--batch'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        cat.stdin.write(data)
        cat.stdin.close()
        for oid, index in part:
            head = cat.stdout.readline().split()
            if len(head) != 3 or head[0].decode() != oid or head[1] != b'blob':
                raise SystemExit(f'unexpected answer for {oid}: {head}')
            body = cat.stdout.read(int(head[2]))
            cat.stdout.read(1)
            if body[:2] != b'\x1f\x8b':
                raise SystemExit(f'{oid} is not a gzip file')
            (a.out / f'{index:06d}.json.gz').write_bytes(body)
        cat.wait()
    have = sorted(f.name for f in a.out.glob('*.json.gz'))
    (a.out / 'MANIFEST.json').write_text(json.dumps(dict(repo=REPO, branch=a.branch, tip=tip, first=a.first, last=a.last, episodes=len(have),
                                                         fetched_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())), indent=1))
    print(json.dumps(dict(episodes=len(have), tip=tip[:10])))


if __name__ == '__main__':
    main()
