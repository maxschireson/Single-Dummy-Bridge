#!/usr/bin/env python3
"""Fetch every episode of some feed branches from GitHub, one file per distinct blob.

  python fetch_feeds.py --out DIR --work DIR --manifest FILE [--seen DIR ...] [--limit N] [--jobs 6] PATTERN [PATTERN ...]

PATTERN is a branch name or a shell pattern (arena-gen6-*). An episode is any path */episodes/*.json.gz at a
branch's tip. Each distinct blob is written once as DIR/<blob id>.json.gz; a blob already in DIR or in a --seen
directory is skipped, so a second run into a new DIR fetches only what arrived since. Nothing but blobs that
are episodes is downloaded (blobless fetch of the tips, then the blobs by id). The manifest records the tips,
the counts per branch and the time, so a training set can say exactly what it was built from.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from fnmatch import fnmatch
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

REPO = os.environ.get('P41_REPO', 'https://github.com/maxschireson/Single-Dummy-Bridge')
EPISODE = re.compile(r'(^|/)episodes/[^/]+\.json\.gz$')


def git(git_dir, *args, data=None, check=True):
    r = subprocess.run(['git', '--git-dir', str(git_dir), *args], input=data, capture_output=True)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args[:3])} failed: {r.stderr.decode(errors='replace')[-400:]}")
    return r


def store(path):
    if not (path / 'HEAD').exists():
        subprocess.run(['git', 'init', '--bare', '-q', str(path)], check=True)
        git(path, 'remote', 'add', 'origin', REPO)
        git(path, 'config', 'remote.origin.promisor', 'true')
        git(path, 'config', 'remote.origin.partialclonefilter', 'blob:none')
        git(path, 'config', 'gc.auto', '0')
    return path


def fetch_chunk(job):
    index, repo, ids, out = job
    data = ('\n'.join(ids) + '\n').encode()
    for attempt in range(4):
        r = git(repo, '-c', 'fetch.negotiationAlgorithm=noop', 'fetch', '-q', '--no-tags', '--no-write-fetch-head',
                '--recurse-submodules=no', '--filter=blob:none', 'origin', '--stdin', data=data, check=False)
        if r.returncode == 0:
            break
        time.sleep(3 * (attempt + 1))
    else:
        raise RuntimeError(f"chunk {index}: fetch failed: {r.stderr.decode(errors='replace')[-300:]}")
    p = subprocess.Popen(['git', '--git-dir', str(repo), 'cat-file', '--batch'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    p.stdin.write(data)
    p.stdin.close()
    size = 0
    for oid in ids:
        head = p.stdout.readline().split()
        if len(head) != 3 or head[0].decode() != oid or head[1] != b'blob':
            raise RuntimeError(f'chunk {index}: unexpected answer for {oid}: {head}')
        n = int(head[2])
        body = p.stdout.read(n)
        p.stdout.read(1)
        if len(body) != n or body[:2] != b'\x1f\x8b':
            raise RuntimeError(f'chunk {index}: {oid} is not a complete gzip file')
        tmp = out / (oid + '.tmp')
        tmp.write_bytes(body)
        tmp.replace(out / (oid + '.json.gz'))
        size += n
    p.wait()
    shutil.rmtree(repo / 'objects' / 'pack', ignore_errors=True)       # the files are written; drop the pack
    (repo / 'objects' / 'pack').mkdir(parents=True, exist_ok=True)
    return len(ids), size


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--seen', type=Path, action='append', default=[])
    p.add_argument('--limit', type=int, default=0, help='at most this many new blobs (for a test)')
    p.add_argument('--jobs', type=int, default=6)
    p.add_argument('--chunk', type=int, default=400)
    p.add_argument('patterns', nargs='+')
    a = p.parse_args()
    started = time.time()
    a.out.mkdir(parents=True, exist_ok=True)
    a.work.mkdir(parents=True, exist_ok=True)
    base = store(a.work / 'base.git')
    heads = {}
    for line in git(base, 'ls-remote', 'origin', 'refs/heads/*').stdout.decode().splitlines():
        oid, ref = line.split('\t')
        name = ref[len('refs/heads/'):]
        if any(fnmatch(name, pat) for pat in a.patterns):
            heads[name] = oid
    if not heads:
        raise SystemExit('no branch matches')
    names = sorted(heads)
    for i in range(0, len(names), 12):
        git(base, 'fetch', '-q', '--no-tags', '--depth=1', '--filter=blob:none', 'origin',
            *[f'+refs/heads/{n}:refs/feeds/{n}' for n in names[i:i + 12]])
    have = {f.name.split('.')[0] for d in (a.out, *a.seen) if d.exists() for f in d.iterdir() if f.name.endswith('.json.gz')}
    branches, new, first = {}, [], {}
    for name in names:
        tip = git(base, 'rev-parse', f'refs/feeds/{name}').stdout.decode().strip()
        when = git(base, 'log', '-1', '--format=%cI', tip).stdout.decode().strip()
        total = fresh = 0
        for line in git(base, 'ls-tree', '-r', tip).stdout.decode().splitlines():
            meta, path = line.split('\t', 1)
            if not EPISODE.search(path):
                continue
            oid = meta.split()[2]
            total += 1
            if oid in have or oid in first:
                continue
            first[oid] = name
            new.append(oid)
            fresh += 1
        branches[name] = dict(tip=tip, tip_time=when, episodes=total, new=fresh)
    if a.limit:
        new = new[:a.limit]
    print(f"{len(names)} branches, {sum(b['episodes'] for b in branches.values())} episode paths, {len(new)} new blobs to fetch", flush=True)
    chunks = [new[i:i + a.chunk] for i in range(0, len(new), a.chunk)]
    repos = [store(a.work / f'w{j}.git') for j in range(a.jobs)]
    done = size = 0

    def worker(j):
        nonlocal done, size
        for index in range(j, len(chunks), a.jobs):
            n, s = fetch_chunk((index, repos[j], chunks[index], a.out))
            done += n
            size += s
            print(f"{done} of {len(new)} blobs, {size / 2**30:.2f} GB, {round(time.time() - started)} s", flush=True)

    with ThreadPoolExecutor(a.jobs) as pool:
        for f in [pool.submit(worker, j) for j in range(a.jobs)]:
            f.result()
    summary = dict(repo=REPO, patterns=a.patterns, finished_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                   seconds=round(time.time() - started), new_blobs=len(new), new_bytes=size, branches=branches,
                   new_by_branch={n: sum(1 for o in new if first[o] == n) for n in names})
    a.manifest.parent.mkdir(parents=True, exist_ok=True)
    a.manifest.write_text(json.dumps(summary, indent=1))
    print(json.dumps({k: summary[k] for k in ('finished_utc', 'seconds', 'new_blobs', 'new_bytes')}))


if __name__ == '__main__':
    main()
